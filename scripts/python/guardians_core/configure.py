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

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import speckit, yamlio
from .common import (EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, NAMES, GuardiansError, eol_of, read_raw, rel, run, version_satisfies,
                     write_text)
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
        notes = [line.strip()[len("NOTE: "):] for line in self.lines if line.strip().startswith("NOTE: ")]
        return {"changes": self.changes, "notes": notes, "siblings": self.siblings,
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


def keep_speckit_catalogs(project: Project, cfg: Config, outcome: Outcome, dry_run: bool) -> None:
    """A project catalog file replaces Spec Kit's catalogs. One that lists only the family's (what a bare
    `specify extension catalog add <family catalog>` creates) hides every other extension from search, info and
    update: add Spec Kit's default and community catalogs back, as `specify ... catalog add` would write them.
    `checks.catalogs_keep_defaults: off` leaves the files alone."""
    if cfg.severity("catalogs_keep_defaults") == "off":
        return
    for kind in speckit.CATALOGS:
        stack = speckit.CatalogStack(project.root, kind)
        if not stack.repairable():
            continue
        add = stack.builtin_to_add()
        original = read_raw(stack.path)
        text = speckit.append_catalogs(original, add)
        if text is not None:
            wanted = [{"name": n, "url": u, "priority": p, "install_allowed": a, "description": ""} for n, u, p, a in add]
            try:
                before = (yamlio.loads(original, str(stack.path)) or {}).get("catalogs")
                after = (yamlio.loads(text, str(stack.path)) or {}).get("catalogs")
            except (GuardiansError, AttributeError):
                before = after = None
            if not isinstance(before, list) or after != before + wanted:
                text = None     # the edit would change more than the appended entries: leave the file to a person
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

def _missing(project: Project) -> List[speckit.IntegrationEvents]:
    declared = project.declared_events()
    return [i for i in speckit.event_wiring(project.root, declared) if i.state == "missing"] if declared else []


def _describe(items: List[speckit.IntegrationEvents]) -> str:
    return "; ".join(f"{', '.join(NAMES[e] for e in i.missing)} for {i.key}" for i in items)


def wire_agent_events(project: Project, cfg: Config, outcome: Outcome, dry_run: bool) -> None:
    """`specify bundle install` does not wire the extensions' agent events (`extension add` and `enable` do), so
    archiGuard's edit guard and auditGuard's guard would never run. Spec Kit rewires every enabled extension's events
    on `enable`; Guardians has no hooks or events of its own. Side effects of the two commands, both put back or
    reported: Spec Kit rewrites .specify/extensions.yml (same content, the platform's line ending - the file's own is
    restored) and `enable` recreates a deleted guardians-config.yml from its template. `checks.agent_events_wired:
    off` leaves the events alone."""
    missing = _missing(project)
    if not missing or cfg.severity("agent_events_wired") == "off":
        return
    what = _describe(missing)
    unreadable = [i for i in missing if i.unreadable]
    if unreadable:      # Spec Kit skips a settings file it cannot parse; toggling would only repeat on every run
        outcome.lines.append(f"  NOTE: the agent events of {_describe(unreadable)} are not wired: Spec Kit cannot add them to "
                             f"{', '.join(str(i.file) for i in unreadable)} (not plain JSON, for example comments); make it "
                             "plain JSON, then run guardians configure again")
        missing = [i for i in missing if not i.unreadable]
        if not missing:
            return
        what = _describe(missing)
    guardians = project.sibling("guardians")
    blocker = speckit.toggle_blocker(project.root, guardians.installed, project.extension_enabled("guardians"))
    if blocker:
        command = "specify extension enable guardians" if blocker.startswith("Guardians is disabled") else speckit.WIRE_EVENTS
        outcome.lines.append(f"  NOTE: the agent events of {what} are not wired ({blocker}): run {command}")
        return
    if dry_run:
        outcome.changes.append(f"agent events of {what}: {speckit.WIRE_EVENTS} (Spec Kit wires them)")
        return
    registry = project.registry_path
    original = read_raw(registry) if registry.is_file() else None
    config_existed = guardians.config_path.is_file()
    command = speckit.specify_command() or ["specify"]
    failure = ""
    for action in ("disable", "enable"):
        code, out, err = run(command + ["extension", action, "guardians"], project.root)
        if code != 0:
            failure = f"specify extension {action} guardians exited {code} ({((err or out).strip().splitlines() or [''])[-1][:200]})"
            break
    if failure and not project.extension_enabled("guardians"):
        run(command + ["extension", "enable", "guardians"], project.root)   # never leave Guardians disabled
        if not project.extension_enabled("guardians"):
            raise GuardiansError(f"{failure}: Guardians is left disabled in Spec Kit - run specify extension enable guardians")
    if original is not None and registry.is_file():
        # Spec Kit dumped .specify/extensions.yml again (platform line ending, no comments): the same data gets the
        # original bytes back; anything else is reported
        text = read_raw(registry)
        if text != original:
            try:
                same = yamlio.loads(text, str(registry)) == yamlio.loads(original, str(registry))
            except GuardiansError:
                same = False
            if same:
                write_text(registry, original)
            else:
                write_text(registry, text.replace("\r\n", "\n").replace("\n", eol_of(original)))
                outcome.changes.append(f"{rel(registry, project.root)}: rewritten by Spec Kit during the toggle")
    if not config_existed and guardians.config_path.is_file():
        outcome.changes.append(f"{rel(guardians.config_path, project.root)}: created by Spec Kit from the template "
                               "(`specify extension enable` scaffolds a missing config)")
    still = _describe(_missing(project))
    if failure:
        outcome.lines.append(f"  NOTE: {failure}; the agent events of {what} are not wired: run {speckit.WIRE_EVENTS}")
    elif still:
        warning = next((line.strip() for line in (out + "\n" + err).splitlines()
                        if re.search(r"⚠|warning|fail|could not|skipp", line, re.I)), "")[:200]
        outcome.lines.append(f"  NOTE: Spec Kit did not wire the agent events of {still}"
                             + (f" (it said: {warning})" if warning else "") + " - see agent_events_wired below")
    else:
        outcome.changes.append(f"agent events of {what}: wired by Spec Kit ({speckit.WIRE_EVENTS}; it refreshes every "
                               "enabled extension's events)")


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
        keep_speckit_catalogs(project, cfg, outcome, dry_run)
        project.reset()
        if siblings:
            outcome.lines.append("  Siblings:")
            run_siblings(project, cfg, outcome, dry_run, verbose)
            outcome.lines.append("")
            project.reset()
        wire_agent_events(project, cfg, outcome, dry_run)
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
