"""guardians configure: cross-wire, run the three configures in order, order the hooks, report.

Order of work (why: scopeGuard's own configure must already see `embedded` so it switches its hooks off):
  1. cross-wiring edits   - scopeGuard `integration: embedded`; archiGuard's edit guard covers the audit trail;
                            Spec Kit's catalogs back in a catalog file that lists only the family's
  2. the siblings' configure commands, in the configured order
  3. the agent events     - `specify extension disable/enable guardians` when a bundle install left them unwired
                            (Spec Kit rewrites .specify/extensions.yml then, so this comes before step 4)
  4. hook priorities in .specify/extensions.yml (auditGuard first and last on a shared event)
  5. the verify report
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import speckit, yamlio
from .common import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, NAMES, GuardiansError, read_raw, rel, run, version_satisfies, write_text
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


def _parses(text: str, path: Path) -> None:
    """Raise GuardiansError when an edited text no longer parses (the line endings do not matter to the readers)."""
    yamlio.loads(text.replace("\r\n", "\n"), str(path))


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
        outcome.lines.append(f"  NOTE: {rel(sg.config_path, project.root)} not found: {sg.config_hint()}, then run guardians configure again")
        return
    if sg.get("integration") == "embedded":
        return
    text, old, changed = set_top_level_scalar(read_raw(sg.config_path), "integration", "embedded")
    if changed:
        _parses(text, sg.config_path)  # refuse to leave a file that no longer parses
        _write(project, sg.config_path, text, f"integration: {old or '(absent)'} -> embedded (archiGuard runs the scope gate)",
               outcome, dry_run)


def wire_edit_guard(project: Project, outcome: Outcome, dry_run: bool) -> None:
    ag, au = project.sibling("archiguard"), project.sibling("auditguard")
    if not (ag.installed and au.installed):
        return
    if not ag.config_path.is_file():
        outcome.lines.append(f"  NOTE: {rel(ag.config_path, project.root)} not found: {ag.config_hint()}, then run guardians configure again")
        return
    current = ag.get("edit_guard", "always_readonly", default=ARCHIGUARD_READONLY)
    current = [str(p) for p in current] if isinstance(current, list) else []
    missing = [p for p in au.audit_readonly() if p not in current]
    if not missing:
        return
    text, added = append_to_list(read_raw(ag.config_path), "edit_guard", "always_readonly", missing)
    if not added:
        outcome.lines.append(f"  NOTE: could not edit edit_guard.always_readonly in {rel(ag.config_path, project.root)} "
                             f"(unexpected shape); add {', '.join(missing)} by hand")
        return
    _parses(text, ag.config_path)
    _write(project, ag.config_path, text, f"edit_guard.always_readonly += {', '.join(added)}", outcome, dry_run)


def keep_speckit_catalogs(project: Project, outcome: Outcome, dry_run: bool) -> None:
    """A project catalog file replaces Spec Kit's catalogs. One that lists only the family's (what a bare
    `specify extension catalog add <family catalog>` creates) hides every other extension from search, info and
    update: add Spec Kit's default and community catalogs back, as `specify ... catalog add` would write them."""
    for kind in speckit.CATALOGS:
        stack = speckit.CatalogStack(project.root, kind)
        if not stack.repairable():
            continue
        add = stack.builtin_to_add()
        text = speckit.append_catalogs(read_raw(stack.path), add)
        if text is not None:
            data = yamlio.loads(text.replace("\r\n", "\n"), str(stack.path))
            items = data.get("catalogs") if isinstance(data, dict) else None
            urls = [str(e.get("url", "")).strip() for e in items or [] if isinstance(e, dict) and str(e.get("url", "")).strip()]
            if urls != stack.urls + [url for _name, url, _prio, _allowed in add]:
                text = None
        if text is None:
            outcome.lines.append(f"  NOTE: could not edit {stack.label} (unexpected shape); add Spec Kit's catalogs by hand: "
                                 f"{stack.add_commands()}")
            continue
        names = ", ".join(f"{name} (priority {prio})" for name, _url, prio, _allowed in add)
        _write(project, stack.path, text, f"catalogs += {names} - Spec Kit's own {kind} catalogs, which this file replaced",
               outcome, dry_run)


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


# ----- 3. the agent events -------------------------------------------------------------------------------

def wire_agent_events(project: Project, outcome: Outcome, dry_run: bool) -> None:
    """`specify bundle install` does not wire the extensions' agent events (`extension add` and `enable` do), so
    archiGuard's edit guard and auditGuard's guard would never run. Spec Kit wires them on `enable`; Guardians has no
    hooks or events of its own, so disabling and enabling it changes nothing else."""
    declared = project.declared_events()
    missing = [i for i in speckit.event_wiring(project.root, declared) if i.state == "missing"] if declared else []
    if not missing:
        return
    what = "; ".join(f"{', '.join(NAMES[e] for e in i.missing)} for {i.key}" for i in missing)
    if dry_run:
        outcome.changes.append(f"agent events of {what}: {speckit.WIRE_EVENTS} (Spec Kit wires them)")
        return
    command = speckit.specify_command()
    blocker = ""
    if not project.sibling("guardians").installed:
        blocker = "Guardians is not installed in this project"
    elif not project.extension_enabled("guardians"):
        blocker = "Guardians is disabled in Spec Kit"
    elif speckit.init_ai(project.root) == "generic":
        blocker = "the generic integration"
    elif command is None:
        blocker = "specify is not on PATH"
    if blocker:
        outcome.lines.append(f"  NOTE: the agent events of {what} are not wired ({blocker}): run {speckit.WIRE_EVENTS}")
        return
    for action in ("disable", "enable"):
        code, out, err = run(command + ["extension", action, "guardians"], project.root)
        if code != 0:
            tail = ((err or out).strip().splitlines() or [""])[-1][:200]
            if action == "disable":
                outcome.lines.append(f"  NOTE: specify extension disable guardians exited {code} ({tail}); the agent events "
                                     f"of {what} are not wired: run {speckit.WIRE_EVENTS}")
                return
            raise GuardiansError(f"specify extension enable guardians exited {code} ({tail}): Guardians is left disabled "
                                 "in Spec Kit - run specify extension enable guardians")
    outcome.changes.append(f"agent events of {what}: wired by Spec Kit ({speckit.WIRE_EVENTS})")
    still = [i for i in speckit.event_wiring(project.root, project.declared_events()) if i.state == "missing"]
    if still:
        outcome.lines.append("  NOTE: Spec Kit did not wire the agent events of "
                             + "; ".join(f"{', '.join(NAMES[e] for e in i.missing)} for {i.key}" for i in still)
                             + " (see agent_events_wired below)")


# ----- 4. hook order -------------------------------------------------------------------------------------

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

    text, found = edit_hook_entries(read_raw(path), "priority", decide)
    if not found:
        return
    _parses(text, path)
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
        keep_speckit_catalogs(project, outcome, dry_run)
        project.reset()
        if siblings:
            outcome.lines.append("  Siblings:")
            run_siblings(project, cfg, outcome, dry_run, verbose)
            outcome.lines.append("")
            project.reset()
        wire_agent_events(project, outcome, dry_run)
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
