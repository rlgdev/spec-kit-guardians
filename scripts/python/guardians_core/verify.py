"""guardians verify: do the three Guardians' configurations agree? Reads everything, writes nothing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .common import GUARDIANS, NAMES, SIBLINGS, GuardiansError, rel, version_satisfies
from .config import CHECKS, Config
from .siblings import (ARCHIGUARD_READONLY, ARCHIGUARD_SCOPE_RANGE, AUDITGUARD_COLLECTOR_RANGES,
                       AUDITGUARD_GITATTRIBUTES, Project, Sibling)

MARK = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]", "off": "[--]  ", "na": "[--]  "}


class Check:
    def __init__(self, check_id: str, severity: str):
        self.id = check_id
        self.severity = severity
        self.status = "ok"
        self.message = ""
        self.fix = ""

    def problem(self, message: str, fix: str = "") -> "Check":
        self.status = self.severity if self.severity in ("fail", "warn") else "off"
        self.message, self.fix = message, fix
        return self

    def ok(self, message: str) -> "Check":
        self.status, self.message = "ok", message
        return self

    def na(self, message: str) -> "Check":
        self.status, self.message = "na", message
        return self

    def data(self) -> Dict[str, str]:
        return {"id": self.id, "severity": self.severity, "status": self.status, "message": self.message, "fix": self.fix}


class Report:
    def __init__(self, root: Path):
        self.root = root
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.checks: List[Check] = []
        self.notes: List[str] = []

    @property
    def status(self) -> str:
        statuses = {c.status for c in self.checks}
        return "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok"

    @property
    def failed(self) -> List[Check]:
        return [c for c in self.checks if c.status == "fail"]

    def text(self) -> str:
        lines = ["  Tools:"]
        for ext in GUARDIANS:
            tool = self.tools.get(ext, {})
            name = f"{NAMES[ext]:<10}"
            if not tool.get("installed"):
                lines.append(f"    {name} : not installed")
                continue
            if ext == "guardians":
                lines.append(f"    {name} : {tool['version']}")
                continue
            integration = tool["integration"]
            if tool.get("effective_integration") and tool["effective_integration"] != integration:
                integration += f" -> {tool['effective_integration']}"
            extra = ""
            if ext == "archiguard" and tool.get("scope_in_pipeline") is not None:
                extra = f" | scope gate {'in' if tool['scope_in_pipeline'] else 'not in'} pipeline"
            if ext == "archiguard":
                extra += f" | preset {'installed' if tool.get('preset') else 'missing'}"
            lines.append(f"    {name} : {tool['version']} | integration {integration} | mode {tool['mode']} | "
                         f"hooks {tool['hooks_on']}/{tool['hooks']}{extra}")
            if tool.get("status_error"):
                lines.append(f"    {'':<10}   NOTE: its configure --dry-run --json failed: {tool['status_error']}")
        lines += ["", "  Checks:"]
        for check in self.checks:
            lines.append(f"    {MARK[check.status]} {check.id:<27} {check.message}")
            if check.status in ("warn", "fail") and check.fix:
                lines.append(f"           {'':<27} fix: {check.fix}")
        for note in self.notes:
            lines.append(f"  NOTE: {note}")
        counts = {s: sum(1 for c in self.checks if c.status == s) for s in ("ok", "warn", "fail")}
        lines += ["", f"  RESULT: {self.status.upper()} | {counts['ok']} ok, {counts['warn']} warnings, {counts['fail']} failures"]
        return "\n".join(lines)

    def data(self) -> Dict[str, Any]:
        return {"version": __version__, "root": str(self.root), "status": self.status, "tools": self.tools,
                "checks": [c.data() for c in self.checks], "notes": self.notes}


# --------------------------------------------------------------------------- #

def _tools(project: Project, report: Report) -> None:
    for ext in GUARDIANS:
        sib = project.sibling(ext)
        if not sib.installed:
            report.tools[ext] = {"installed": False}
            continue
        tool: Dict[str, Any] = {"installed": True, "version": sib.version}
        if ext != "guardians":
            on, registered = project.hook_counts(ext)
            tool.update({"integration": sib.integration(), "effective_integration": sib.effective_integration(),
                         "mode": sib.mode(), "hooks_on": on, "hooks": registered})
            if sib.status() is None and sib.status_error:
                tool["status_error"] = sib.status_error
            if ext == "archiguard":
                tool["scope_in_pipeline"] = sib.scope_in_pipeline()
                tool["preset"] = project.preset_installed(project.preset_of("archiguard"))
        report.tools[ext] = tool


def _cfg_path(sib: Sibling) -> str:
    return rel(sib.config_path, sib.root)


def _configure_fix(sib: Sibling, what: str) -> str:
    """The fix for a cross-wiring check: guardians configure, once the sibling's config file exists."""
    first = "" if sib.config_path.is_file() else f"{sib.config_hint()}, then "
    return f"{first}guardians configure ({what})"


def check_installed(project: Project, c: Check) -> Check:
    missing = [ext for ext in GUARDIANS if not project.sibling(ext).installed]
    if missing:
        return c.problem(f"not installed: {', '.join(missing)}", "specify bundle install guardians")
    return c.ok("scopeguard, archiguard, auditguard, guardians")


def check_preset_matches_integration(project: Project, c: Check) -> Check:
    ag = project.sibling("archiguard")
    problems, fixes = [], []
    if project.preset_installed(project.preset_of("scopeguard")):
        problems.append("scopeguard-templates is installed (archiGuard wraps the commands; the scope gate would run twice)")
        fixes.append("specify preset remove scopeguard-templates")
    if ag.installed:
        preset = project.preset_installed(project.preset_of("archiguard"))
        configured, effective = ag.integration(), ag.effective_integration()
        if configured == "inline" and not preset:
            problems.append("archiGuard is configured inline but archiguard-templates is not installed (it fell back to hooks)")
            fixes.append("specify bundle install guardians (installs the preset) - or set integration: hooks in " + _cfg_path(ag))
        elif preset and effective == "hooks":
            problems.append("archiguard-templates is installed but archiGuard runs through hooks (gates would run twice)")
            fixes.append(f"set integration: inline in {_cfg_path(ag)} - or specify preset remove archiguard-templates")
    if problems:
        return c.problem("; ".join(problems), " / ".join(fixes))
    if not ag.installed:
        return c.na("archiGuard not installed")
    return c.ok(f"archiguard-templates {'installed' if project.preset_installed(project.preset_of('archiguard')) else 'absent'}, "
                f"archiGuard integration {ag.effective_integration()}; scopeguard-templates absent")


def check_versions_in_range(project: Project, c: Check) -> Check:
    sg, ag, au = (project.sibling(e) for e in SIBLINGS)
    bad, seen = [], []
    if ag.installed and sg.installed:
        if ag.get("gates") is None:
            wanted: Optional[str] = ARCHIGUARD_SCOPE_RANGE      # archiGuard's own default registration
        elif ag.get("gates", "scope") is None:
            wanted = None                                       # the scope gate is not registered
        else:
            wanted = ag.get("gates", "scope", "version")
        if wanted and not version_satisfies(sg.version or "0", str(wanted)):
            bad.append(f"archiGuard gates.scope.version {wanted} does not accept scopeGuard {sg.version}")
        elif wanted:
            seen.append(f"scopeGuard {sg.version} in archiGuard's {wanted}")
    if au.installed:
        for ext, sib in (("scopeguard", sg), ("archiguard", ag)):
            if not sib.installed:
                continue
            wanted = au.get("collectors", ext, "version", default=AUDITGUARD_COLLECTOR_RANGES[ext])
            if not version_satisfies(sib.version or "0", str(wanted)):
                bad.append(f"auditGuard collectors.{ext}.version {wanted} does not accept {NAMES[ext]} {sib.version}")
            else:
                seen.append(f"{NAMES[ext]} {sib.version} in auditGuard's {wanted}")
    if bad:
        return c.problem("; ".join(bad), "bump the bundle (new tested combination) or widen the range in the config named")
    if not seen:
        return c.na("fewer than two Guardians installed")
    return c.ok("; ".join(seen))


def check_scopeguard_embedded(project: Project, c: Check) -> Check:
    sg, ag = project.sibling("scopeguard"), project.sibling("archiguard")
    if not (sg.installed and ag.installed):
        return c.na("needs scopeGuard and archiGuard")
    in_pipeline = ag.scope_in_pipeline()
    if in_pipeline is None:
        return c.problem(f"cannot tell whether archiGuard runs the scope gate ({ag.status_error or 'no status'})",
                         "bash .specify/extensions/archiguard/scripts/bash/archiguard.sh configure --dry-run")
    if not in_pipeline:
        return c.na("archiGuard's pipeline does not run the scope gate; scopeGuard keeps its own integration")
    if not version_satisfies(sg.version or "0", ">=0.4.0"):
        return c.problem(f"scopeGuard {sg.version} has no embedded integration (needs >= 0.4.0)", "bundle pins scopeGuard >= 0.4.0")
    integration = sg.integration()
    if integration != "embedded":
        return c.problem(f"scopeGuard integration is {integration} while archiGuard runs the scope gate",
                         _configure_fix(sg, f"sets integration: embedded in {_cfg_path(sg)}"))
    return c.ok("scopeGuard integration embedded (archiGuard runs the scope gate)")


def check_auditguard_integration(project: Project, c: Check) -> Check:
    au = project.sibling("auditguard")
    if not au.installed:
        return c.na("auditGuard not installed")
    integration = au.integration()
    if integration not in ("hooks", "workflow"):
        return c.problem(f"auditGuard integration {integration!r} is not hooks or workflow", f"{_cfg_path(au)} integration")
    if integration == "workflow":
        return c.ok("auditGuard integration workflow (hooks print skipped; the siblings' workflow steps and CI record)")
    return c.ok("auditGuard integration hooks")


def _priority(entry: Dict[str, Any]) -> int:
    try:
        value = int(entry.get("priority", 10))
    except (TypeError, ValueError):
        value = 10
    return value if value >= 1 else 10


def check_hook_order(project: Project, c: Check) -> Check:
    au = project.sibling("auditguard")
    if not au.installed:
        return c.na("auditGuard not installed")
    if au.effective_integration() != "hooks":
        return c.na(f"auditGuard integration {au.effective_integration()}: no hooks to order")
    shared, wrong = 0, []
    for event, entries in sorted(project.hooks().items()):
        guards = [e for e in entries if e.get("extension") in SIBLINGS and e.get("enabled", True)]
        if len(guards) < 2:
            continue
        shared += 1
        audit = [e for e in guards if e.get("extension") == "auditguard"]
        others = [e for e in guards if e.get("extension") != "auditguard"]
        for a in audit:
            if event.startswith("before_") and any(_priority(a) >= _priority(o) for o in others):
                wrong.append(f"{event}: {a.get('command')} priority {_priority(a)} does not run before the gates")
            if event.startswith("after_") and any(_priority(a) <= _priority(o) for o in others):
                wrong.append(f"{event}: {a.get('command')} priority {_priority(a)} does not run after the gates")
    if wrong:
        return c.problem("; ".join(wrong), "guardians configure (auditGuard before_* 1, after_* 90, gates 10)")
    if not shared:
        return c.ok("no event is shared by two Guardians (gates inline / embedded); auditGuard records alone")
    return c.ok(f"auditGuard records first and last on {shared} shared event(s)")


def check_hooks_match_integration(project: Project, c: Check) -> Check:
    problems, fixes, seen = [], [], []
    for ext in SIBLINGS:
        sib = project.sibling(ext)
        if not sib.installed:
            continue
        on, registered = project.hook_counts(ext)
        effective = sib.effective_integration()
        launcher = f".specify/extensions/{ext}/scripts/bash/{ext}.sh configure"
        if effective != "hooks" and on:
            problems.append(f"{NAMES[ext]}: {on} hook(s) enabled but integration {effective}")
            fixes.append(launcher)
        elif effective == "hooks" and registered and not on:
            problems.append(f"{NAMES[ext]}: integration hooks but none of its {registered} hooks is enabled")
            fixes.append(launcher)
        else:
            seen.append(f"{NAMES[ext]} {on}/{registered} ({effective})")
    if problems:
        return c.problem("; ".join(problems), " / ".join(f"bash {f}" for f in sorted(set(fixes))))
    if not seen:
        return c.na("no Guardian installed")
    return c.ok("; ".join(seen))


def check_git_base_agrees(project: Project, c: Check) -> Check:
    ag, au = project.sibling("archiguard"), project.sibling("auditguard")
    if not (ag.installed and au.installed):
        return c.na("needs archiGuard and auditGuard")
    a, b = str(ag.get("git", "base", default="main")), str(au.get("golden", "git", "base", default="main"))
    if a != b:
        return c.problem(f"archiguard git.base={a}, auditguard golden.git.base={b}",
                         f"{_cfg_path(ag)} git.base / {_cfg_path(au)} golden.git.base - a person decides which is right")
    return c.ok(f"both use base branch {a}")


def check_edit_guard_covers_audit(project: Project, c: Check) -> Check:
    ag, au = project.sibling("archiguard"), project.sibling("auditguard")
    if not (ag.installed and au.installed):
        return c.na("needs archiGuard and auditGuard")
    enabled = ag.get("edit_guard", "enabled", default=True)
    readonly = ag.get("edit_guard", "always_readonly", default=ARCHIGUARD_READONLY)
    readonly = [str(p) for p in readonly] if isinstance(readonly, list) else []
    missing = [p for p in au.audit_readonly() if p not in readonly]
    if not enabled:
        return c.problem("archiGuard edit guard is disabled: the audit trail is protected by auditGuard's guard only",
                         f"{_cfg_path(ag)} edit_guard.enabled: true")
    if missing:
        return c.problem(f"archiGuard edit_guard.always_readonly lacks {', '.join(missing)}",
                         _configure_fix(ag, f"appends them in {_cfg_path(ag)}"))
    return c.ok(f"archiGuard's edit guard covers {', '.join(au.audit_readonly())}")


def check_modes_agree(project: Project, c: Check) -> Check:
    sg, ag, au = (project.sibling(e) for e in SIBLINGS)
    if not (sg.installed and ag.installed):
        return c.na("needs scopeGuard and archiGuard")
    audit = f"; auditGuard {au.mode()} (records, not compared)" if au.installed else ""
    if sg.mode() != ag.mode():
        return c.problem(f"scopeGuard mode {sg.mode()}, archiGuard mode {ag.mode()}{audit}",
                         f"{_cfg_path(sg)} mode / {_cfg_path(ag)} mode")
    return c.ok(f"scopeGuard and archiGuard {ag.mode()}{audit}")


def check_gitattributes(project: Project, c: Check) -> Check:
    au = project.sibling("auditguard")
    if not au.installed:
        return c.na("auditGuard not installed")
    wanted = [line.format(audit=au.audit_root()) for line in AUDITGUARD_GITATTRIBUTES]
    have = [line.strip() for line in (project.read(".gitattributes") or "").splitlines()]
    missing = [w for w in wanted if w not in have]
    if missing:
        return c.problem(f".gitattributes lacks {len(missing)} auditGuard line(s): {'; '.join(missing)}",
                         "bash .specify/extensions/auditguard/scripts/bash/auditguard.sh configure")
    return c.ok("the audit trail is excluded from line-ending conversion")


def _codeowners_covers(patterns: List[str], path: str) -> bool:
    for pattern in patterns:
        p = pattern.strip().lstrip("/")
        if p in ("*", "**"):
            return True
        for suffix in ("/**", "/*", "/"):
            if p.endswith(suffix):
                p = p[: -len(suffix)]
        if p and (path.rstrip("/") == p or path.startswith(p + "/")):
            return True
    return False


def check_codeowners(project: Project, c: Check) -> Check:
    au = project.sibling("auditguard")
    needed = [f"{au.audit_root() if au.installed else 'audit'}/", ".specify/standards/", ".specify/archiguard/",
              ".specify/extensions/"]
    path = project.codeowners()
    if path is None:
        return c.na("no CODEOWNERS file; consider owners for " + ", ".join(needed))
    patterns = []
    for line in project.read(rel(path, project.root)).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line.split()[0])
    missing = [n for n in needed if not _codeowners_covers(patterns, n)]
    if missing:
        return c.problem(f"{rel(path, project.root)} names no owner for {', '.join(missing)}",
                         f"add rules to {rel(path, project.root)}")
    return c.ok(f"{rel(path, project.root)} covers {', '.join(needed)}")


CHECK_FUNCTIONS = {
    "installed": check_installed,
    "preset_matches_integration": check_preset_matches_integration,
    "versions_in_range": check_versions_in_range,
    "scopeguard_embedded": check_scopeguard_embedded,
    "auditguard_integration": check_auditguard_integration,
    "hook_order": check_hook_order,
    "hooks_match_integration": check_hooks_match_integration,
    "git_base_agrees": check_git_base_agrees,
    "edit_guard_covers_audit": check_edit_guard_covers_audit,
    "modes_agree": check_modes_agree,
    "gitattributes": check_gitattributes,
    "codeowners": check_codeowners,
}
assert set(CHECK_FUNCTIONS) == set(CHECKS)


def run_verify(project: Project, cfg: Config) -> Report:
    report = Report(project.root)
    _tools(project, report)
    for check_id in CHECKS:
        check = Check(check_id, cfg.severity(check_id))
        if check.severity == "off":
            check.status, check.message = "off", "switched off in guardians-config.yml"
            report.checks.append(check)
            continue
        try:
            CHECK_FUNCTIONS[check_id](project, check)
        except GuardiansError as exc:  # fail closed: a check that cannot be made is a failure of that check
            check.problem(f"could not check: {exc}", "fix the file named, then run guardians verify again")
        report.checks.append(check)
    return report


def header(root: Path, what: str) -> str:
    return f"Guardians {__version__} | {what} | {root}"
