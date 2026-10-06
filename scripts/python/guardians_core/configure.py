"""guardians configure: cross-wire, run the three configures in order, order the hooks, report.

Order of work (why: scopeGuard's own configure must already see `embedded` so it switches its hooks off):
  1. cross-wiring edits   - scopeGuard `integration: embedded`; archiGuard's edit guard covers the audit trail
  2. the siblings' configure commands, in the configured order
  3. hook priorities in .specify/extensions.yml (auditGuard first and last on a shared event)
  4. the verify report
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import yamlio
from .common import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, NAMES, GuardiansError, read_text, rel, version_satisfies, write_text
from .config import Config
from .edits import append_to_list, edit_hook_entries, set_top_level_scalar
from .siblings import ARCHIGUARD_READONLY, Project
from .verify import Report, header, run_verify


class Outcome:
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.changes: List[str] = []
        self.siblings: List[Dict[str, Any]] = []
        self.report: Optional[Report] = None
        self.exit_code = EXIT_OK

    def data(self) -> Dict[str, Any]:
        return {"changes": self.changes, "siblings": self.siblings,
                "verify": self.report.data() if self.report else None, "exit_code": self.exit_code}


def _write(project: Project, path: Path, text: str, what: str, outcome: Outcome, dry_run: bool) -> None:
    label = f"{rel(path, project.root)}: {what}"
    if not dry_run:
        write_text(path, text)
    outcome.changes.append(label)


# ----- 1. cross-wiring -----------------------------------------------------------------------------------

def wire_scopeguard_embedded(project: Project, outcome: Outcome, dry_run: bool) -> None:
    sg, ag = project.sibling("scopeguard"), project.sibling("archiguard")
    if not (sg.installed and ag.installed):
        return
    if ag.scope_in_pipeline() is not True:
        if ag.scope_in_pipeline() is None:
            outcome.lines.append(f"  NOTE: archiGuard's status is unavailable ({ag.status_error}); scopeGuard's integration left as it is")
        return
    if not version_satisfies(sg.version or "0", ">=0.4.0"):
        outcome.lines.append(f"  NOTE: scopeGuard {sg.version} has no embedded integration (needs 0.4.0); left as it is")
        return
    if not sg.config_path.is_file():
        outcome.lines.append(f"  NOTE: {rel(sg.config_path, project.root)} not found; scopeGuard's configure creates it - run guardians configure again")
        return
    if sg.get("integration") == "embedded":
        return
    text, old, changed = set_top_level_scalar(read_text(sg.config_path), "integration", "embedded")
    if changed:
        yamlio.loads(text, str(sg.config_path))  # refuse to leave a file that no longer parses
        _write(project, sg.config_path, text, f"integration: {old or '(absent)'} -> embedded (archiGuard runs the scope gate)",
               outcome, dry_run)


def wire_edit_guard(project: Project, outcome: Outcome, dry_run: bool) -> None:
    ag, au = project.sibling("archiguard"), project.sibling("auditguard")
    if not (ag.installed and au.installed):
        return
    if not ag.config_path.is_file():
        outcome.lines.append(f"  NOTE: {rel(ag.config_path, project.root)} not found; archiGuard's configure creates it - run guardians configure again")
        return
    current = ag.get("edit_guard", "always_readonly", default=ARCHIGUARD_READONLY)
    current = [str(p) for p in current] if isinstance(current, list) else []
    missing = [p for p in au.audit_readonly() if p not in current]
    if not missing:
        return
    text, added = append_to_list(read_text(ag.config_path), "edit_guard", "always_readonly", missing)
    if not added:
        outcome.lines.append(f"  NOTE: could not edit edit_guard.always_readonly in {rel(ag.config_path, project.root)} "
                             f"(unexpected shape); add {', '.join(missing)} by hand")
        return
    yamlio.loads(text, str(ag.config_path))
    _write(project, ag.config_path, text, f"edit_guard.always_readonly += {', '.join(added)}", outcome, dry_run)


# ----- 2. the siblings' configures ------------------------------------------------------------------------

def run_siblings(project: Project, cfg: Config, outcome: Outcome, dry_run: bool, verbose: bool) -> None:
    for ext in cfg.order:
        sib = project.sibling(ext)
        if not sib.installed:
            outcome.lines.append(f"  {NAMES[ext]:<10} : not installed - skipped")
            continue
        code, text = sib.configure(dry_run)
        first = next((line for line in text.splitlines() if line.strip()), "")
        outcome.siblings.append({"id": ext, "version": sib.version, "exit_code": code, "first_line": first})
        if code != 0:
            outcome.lines.append(f"  {NAMES[ext]:<10} : configure exited {code}")
            outcome.lines += ["    " + line for line in text.splitlines()]
            raise GuardiansError(f"{NAMES[ext]} configure failed (exit {code}); nothing after it ran")
        outcome.lines.append(f"  {NAMES[ext]:<10} : {first}")
        if verbose:
            outcome.lines += ["    " + line for line in text.splitlines()[1:]]


# ----- 3. hook order -------------------------------------------------------------------------------------

def order_hooks(project: Project, cfg: Config, outcome: Outcome, dry_run: bool) -> None:
    path = project.registry_path
    if not path.is_file():
        outcome.lines.append(f"  NOTE: {rel(path, project.root)} not found - no hooks registered yet")
        return

    def decide(ext: str, event: str, _cmd: str, current: Optional[str]) -> Optional[str]:
        now = None
        if current is not None:
            try:
                now = int(current)
            except ValueError:
                now = None
        want = cfg.priority(ext, event, now)
        return None if want is None else str(want)

    text, found = edit_hook_entries(read_text(path), "priority", decide)
    if not found:
        return
    yamlio.loads(text, str(path))
    groups: Dict[Tuple[str, str, str], int] = {}
    for f in found:
        kind = "before_*" if str(f["event"]).startswith("before_") else "after_*" if str(f["event"]).startswith("after_") else str(f["event"])
        key = (str(f["extension"]), kind, f"{f['was'] or '-'} -> {f['now']}")
        groups[key] = groups.get(key, 0) + 1
    summary = ", ".join(f"{ext} {kind} {change} ({n})" for (ext, kind, change), n in sorted(groups.items()))
    _write(project, path, text, f"{len(found)} hook priorit{'y' if len(found) == 1 else 'ies'} set: {summary}", outcome, dry_run)


# ----- all together ---------------------------------------------------------------------------------------

def run_configure(project: Project, cfg: Config, dry_run: bool, siblings: bool, verbose: bool) -> Tuple[str, Outcome]:
    outcome = Outcome()
    outcome.lines.append(header(project.root, "configure" + (" (dry run)" if dry_run else "")))
    outcome.lines.append(f"config: {rel(cfg.path, project.root) if cfg.path else 'built-in defaults'} | order: {', '.join(cfg.order)}")
    outcome.lines.append("")
    try:
        wire_scopeguard_embedded(project, outcome, dry_run)
        wire_edit_guard(project, outcome, dry_run)
        project.reset()
        if siblings:
            outcome.lines.append("  Siblings:")
            run_siblings(project, cfg, outcome, dry_run, verbose)
            outcome.lines.append("")
            project.reset()
        order_hooks(project, cfg, outcome, dry_run)
        project.reset()
    except GuardiansError as exc:
        outcome.lines += ["", f"  ERROR: {exc}"]
        outcome.exit_code = EXIT_ERROR
        return "\n".join(outcome.lines), outcome
    if outcome.changes:
        outcome.lines.append(f"  {'Would change' if dry_run else 'Changed'}:")
        outcome.lines += [f"    {c}" for c in outcome.changes]
    else:
        outcome.lines.append("  No change needed.")
    outcome.lines.append("")
    outcome.report = run_verify(project, cfg)
    outcome.lines.append(outcome.report.text())
    outcome.exit_code = EXIT_FINDINGS if outcome.report.failed else EXIT_OK
    return "\n".join(outcome.lines), outcome
