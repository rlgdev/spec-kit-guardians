"""Test fixtures: a fake Spec Kit project with the three siblings (their real config templates at the pinned
versions, stub launchers that answer `configure --dry-run --json` the way the real ones do), the preset, a hook
registry in Spec Kit's own dump style, the agent integration and the catalog files, and Guardians itself. A stub
`specify` (extension disable / enable) stands in for the Spec Kit CLI; the real one is never called."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SRC = REPO / "scripts" / "python"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import guardians_core  # noqa: E402

GUARDIANS_VERSION = guardians_core.__version__

# The stub siblings are installed at the bundle's pins (the fixtures are their config templates at those tags).
VERSIONS = dict(re.findall(r'\{ id: "(scopeguard|archiguard|auditguard|guardians)",\s+version: "([^"]+)" \}',
                           (REPO / "bundle" / "bundle.yml").read_text(encoding="utf-8")))
assert sorted(VERSIONS) == ["archiguard", "auditguard", "guardians", "scopeguard"], VERSIONS
PRESET_VERSION = re.search(r'\{ id: "archiguard-templates", version: "([^"]+)"',
                           (REPO / "bundle" / "bundle.yml").read_text(encoding="utf-8")).group(1)
NAMES = {"scopeguard": "scopeGuard", "archiguard": "archiGuard", "auditguard": "auditGuard", "guardians": "Guardians"}
DEFAULT_INTEGRATION = {"scopeguard": "inline", "archiguard": "inline", "auditguard": "hooks"}
DEFAULT_MODE = {"scopeguard": "enforce", "archiguard": "enforce", "auditguard": "record"}
AUDIT_COMMANDS = ("specify", "clarify", "plan", "tasks", "analyze", "checklist", "constitution", "converge", "implement",
                  "taskstoissues")
HOOKS: Dict[str, List[Tuple[str, str, bool]]] = {
    "scopeguard": [("before_plan", "speckit.scopeguard.inventory", False), ("after_plan", "speckit.scopeguard.plan", False),
                   ("before_tasks", "speckit.scopeguard.inventory", False), ("after_tasks", "speckit.scopeguard.tasks", False),
                   ("after_implement", "speckit.scopeguard.implement", True)],
    "archiguard": [("before_plan", "speckit.archiguard.planentry", False), ("after_plan", "speckit.archiguard.plangate", False),
                   ("before_tasks", "speckit.archiguard.tasksentry", False), ("after_tasks", "speckit.archiguard.tasksgate", False),
                   ("before_implement", "speckit.archiguard.implemententry", False),
                   ("after_implement", "speckit.archiguard.implementgate", False)],
    "auditguard": [(f"{when}_{cmd}", f"speckit.auditguard.{cmd}{'entry' if when == 'before' else 'exit'}", False)
                   for cmd in AUDIT_COMMANDS for when in ("before", "after")],
}
EVENT_ORDER = [f"{when}_{cmd}" for cmd in AUDIT_COMMANDS for when in ("before", "after")]
# the agent events the real manifests declare (Spec Kit wires them into the agent's settings)
EVENTS = {
    "archiguard": [("pre_tool_use", "speckit.archiguard.editguard"), ("post_tool_use", "speckit.archiguard.editguard")],
    "auditguard": [("session_start", "speckit.auditguard.sessionstart"), ("stop", "speckit.auditguard.stop"),
                   ("session_end", "speckit.auditguard.sessionend"), ("pre_tool_use", "speckit.auditguard.guard")],
}
SPECKIT_RAW = "https://raw.githubusercontent.com/github/spec-kit/main"
FAMILY_RAW = "https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog"


def catalog_file(kind: str, seeded: bool) -> str:
    """A catalog stack file the way `specify <kind> catalog add` writes it: the Guardians catalog alone (the old
    install docs), or after Spec Kit's default and community catalogs (the current install docs)."""
    entry = "- name: {name}\n  url: {url}\n  priority: {priority}\n  install_allowed: {allowed}\n  description: ''\n"
    folder = "extensions" if kind == "extension" else "presets"
    text = "catalogs:\n"
    if seeded:
        text += entry.format(name="default", url=f"{SPECKIT_RAW}/{folder}/catalog.json", priority=1, allowed="true")
        text += entry.format(name="community", url=f"{SPECKIT_RAW}/{folder}/catalog.community.json", priority=20, allowed="false")
    return text + entry.format(name="guardians", url=f"{FAMILY_RAW}/{folder}.json", priority=10, allowed="true")


def claude_settings(commands: Iterable[str]) -> str:
    """.claude/settings.json with Spec Kit's event entries for these commands (none: a bundle install's state)."""
    hooks = [{"type": "command", "command": f'python3 "${{CLAUDE_PROJECT_DIR}}/.specify/events.py" {c} pre_tool_use 10',
              "__speckit_event__": True} for c in commands]
    return json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": hooks}]}} if hooks else {}, indent=2) + "\n"


GITATTRIBUTES = "* text=auto eol=lf\naudit/**/*.jsonl -text\naudit/**/evidence/** -text\naudit/**/seal.json -text\n"
CODEOWNERS = "* @team\naudit/ @lead-architect\n.specify/standards/ @lead-architect\n.specify/archiguard/ @lead-architect\n.specify/extensions/ @lead-architect\n"

STUB = '''#!/usr/bin/env python3
"""Stub of {ext}: answers `configure [--dry-run] [--json]` like the real launcher, records the call, changes nothing."""
import json, re, sys
from pathlib import Path
EXT, NAME, VERSION = "{ext}", "{name}", "{version}"
HERE = Path(__file__).resolve().parent
EXT_DIR = HERE.parent.parent
ROOT = EXT_DIR.parent.parent.parent
cfg_path = EXT_DIR / (EXT + "-config.yml")
cfg = cfg_path.read_text(encoding="utf-8") if cfg_path.is_file() else ""
def top(key, default):
    m = re.search(r"^" + key + r":\\s*([^\\s#]+)", cfg, re.M)
    return m.group(1).strip("'\\"") if m else default
args = sys.argv[1:]
if not args or args[0] != "configure":
    print("stub: only configure is supported", file=sys.stderr); sys.exit(2)
with open(ROOT / ".specify" / "stub-runs.log", "a", encoding="utf-8") as log:
    log.write(EXT + (" dry" if "--dry-run" in args else " run") + "\\n")
fail = EXT_DIR / "FAIL"
if fail.is_file():
    print(NAME + ": configure failed on purpose"); sys.exit(int(fail.read_text().strip() or 3))
integration = top("integration", "{default_integration}")
effective = integration
if EXT == "archiguard" and integration == "inline" and not (ROOT / ".specify" / "presets" / "archiguard-templates").is_dir():
    effective = "hooks"
data = {{"tool": EXT, "version": VERSION, "command": "configure", "dry_run": "--dry-run" in args,
        "integration": integration, "note": None, "hooks": [], "changed": 0}}
if EXT != "auditguard":
    data["effective_integration"] = effective
if EXT in ("scopeguard", "auditguard"):
    data["mode"] = top("mode", "{default_mode}")
if EXT == "archiguard":
    data["scope_in_pipeline"] = not (EXT_DIR / "NO_SCOPE").exists()
    data["readiness"] = {{}}
if "--json" in args:
    print(json.dumps(data, indent=2))
else:
    print(NAME + " " + VERSION + " | configure" + (" (dry run)" if data["dry_run"] else "") + " | integration " + effective)
    print("  hooks: none changed (stub)")
'''

STUB_SPECIFY = '''#!/usr/bin/env python3
"""Stub of the Spec Kit CLI for `extension disable|enable <id>`, as Spec Kit 1.1.1 does it: the registry flag, the
hook registry rewritten with the platform's line ending, a missing config scaffolded on enable, then the agent events
of every enabled extension into .claude/settings.json. Records each call. .specify/SPECIFY_FAIL names the actions that
fail before anything changes; .specify/SPECIFY_FAIL_LATE the ones that fail after the registry flag changed (as an
event-refresh error does); .specify/SPECIFY_NOWIRE makes the event refresh write nothing."""
import json, re, shutil, sys
from pathlib import Path
ROOT = Path.cwd()
args = sys.argv[1:]
with open(ROOT / ".specify" / "stub-specify.log", "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\\n")
if len(args) != 3 or args[0] != "extension" or args[1] not in ("disable", "enable"):
    print("stub: only extension disable|enable <id>", file=sys.stderr); sys.exit(2)
def listed(name):
    path = ROOT / ".specify" / name
    return path.is_file() and args[1] in path.read_text().split()
if listed("SPECIFY_FAIL"):
    print("Error: " + args[1] + " failed on purpose"); sys.exit(1)
reg_path = ROOT / ".specify" / "extensions" / ".registry"
reg = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.is_file() else {"schema_version": "1.0", "extensions": {}}
reg["extensions"].setdefault(args[2], {})["enabled"] = args[1] == "enable"
reg_path.write_text(json.dumps(reg, indent=2), encoding="utf-8")
if listed("SPECIFY_FAIL_LATE"):
    print("Error: " + args[1] + " failed late on purpose"); sys.exit(1)
ext_yml = ROOT / ".specify" / "extensions.yml"
if ext_yml.is_file():
    dumped = "".join(l for l in ext_yml.read_text(encoding="utf-8").splitlines(True) if not l.lstrip().startswith("#"))
    ext_yml.write_text(dumped, encoding="utf-8")   # yaml.dump + write_text: no comments, the platform line ending
ext_dir = ROOT / ".specify" / "extensions" / args[2]
if args[1] == "enable" and (ext_dir / "config-template.yml").is_file() and not (ext_dir / (args[2] + "-config.yml")).is_file():
    shutil.copy(ext_dir / "config-template.yml", ext_dir / (args[2] + "-config.yml"))
    print("Config scaffolded: .specify/extensions/" + args[2] + "/" + args[2] + "-config.yml")
commands = []
for manifest in sorted((ROOT / ".specify" / "extensions").glob("*/extension.yml")):
    if reg["extensions"].get(manifest.parent.name, {}).get("enabled") is False or (ROOT / ".specify" / "SPECIFY_NOWIRE").is_file():
        continue
    text = manifest.read_text(encoding="utf-8")
    block = re.split(r"\\n\\S", text.split("\\nevents:\\n", 1)[1], 1)[0] if "\\nevents:\\n" in text else ""
    commands += re.findall(r"command:\\s*(\\S+)", block)
if (ROOT / ".specify" / "SPECIFY_NOWIRE").is_file():
    print("Warning: event refresh failed for 1 integration(s)")
settings = ROOT / ".claude" / "settings.json"
settings.parent.mkdir(parents=True, exist_ok=True)
hooks = [{"type": "command", "command": "python3 .specify/events.py " + c, "__speckit_event__": True} for c in commands]
settings.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": hooks}]}}, indent=2), encoding="utf-8")
print("Extension '" + args[2] + "' " + args[1] + "d")
'''


@pytest.fixture(autouse=True)
def _speckit_environment(tmp_path_factory, monkeypatch):
    """No user-level catalog files and no catalog variables from this machine; the stub `specify`."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    for var in ("SPECKIT_CATALOG_URL", "SPECKIT_PRESET_CATALOG_URL"):
        monkeypatch.delenv(var, raising=False)
    stub = home / "specify_stub.py"
    stub.write_text(STUB_SPECIFY, encoding="utf-8")
    from guardians_core import speckit
    monkeypatch.setattr(speckit, "specify_command", lambda: [sys.executable, str(stub)])
    return home


def registry_text(enabled: Callable[[str, str], bool], priority: Optional[Callable[[str, str], Optional[int]]] = None,
                  extensions: Iterable[str] = ("scopeguard", "archiguard", "auditguard")) -> str:
    """A .specify/extensions.yml the way Spec Kit's yaml.dump writes it (list items at the key's indent)."""
    lines = ["installed:"] + [f"- {ext}" for ext in extensions] + ["settings:", "  auto_execute_hooks: true", "hooks:"]
    events: Dict[str, List[str]] = {}
    for ext in extensions:
        for event, command, optional in HOOKS[ext]:
            prio = priority(ext, event) if priority else None
            entry = [f"  - extension: {ext}", f"    command: {command}", f"    enabled: {'true' if enabled(ext, event) else 'false'}",
                     f"    optional: {'true' if optional else 'false'}"]
            if prio is not None:
                entry.append(f"    priority: {prio}")
            entry += [f"    prompt: Execute {command}?", f"    description: '({ext}) {event}'", "    condition: null"]
            events.setdefault(event, []).extend(entry)
    for event in sorted(events, key=lambda e: (EVENT_ORDER.index(e) if e in EVENT_ORDER else 99, e)):
        lines.append(f"  {event}:")
        lines += events[event]
    return "\n".join(lines) + "\n"


def all_enabled(_ext: str, _event: str) -> bool:
    return True


def aligned_enabled(ext: str, _event: str) -> bool:
    return ext == "auditguard"


def aligned_priority(ext: str, event: str) -> Optional[int]:
    if ext == "auditguard":
        return 1 if event.startswith("before_") else 90
    return 10


def default_priority(_ext: str, _event: str) -> Optional[int]:
    return 10


class FakeProject:
    def __init__(self, root: Path):
        self.root = root

    def path(self, relative: str) -> Path:
        return self.root / relative

    def config_path(self, ext: str) -> Path:
        return self.root / ".specify" / "extensions" / ext / f"{ext}-config.yml"

    def config(self, ext: str) -> str:
        return self.config_path(ext).read_text(encoding="utf-8")

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:   # Path.write_text(newline=) is 3.10+
            handle.write(text)
        return path

    def replace(self, ext: str, old: str, new: str) -> None:
        text = self.config(ext)
        assert old in text, f"{old!r} not in {ext} config"
        self.write(f".specify/extensions/{ext}/{ext}-config.yml", text.replace(old, new, 1))

    def registry(self) -> str:
        return (self.root / ".specify" / "extensions.yml").read_text(encoding="utf-8")

    def specify_calls(self) -> List[str]:
        """The stub `specify` calls, e.g. ['extension disable guardians', 'extension enable guardians']."""
        log = self.root / ".specify" / "stub-specify.log"
        return log.read_text(encoding="utf-8").splitlines() if log.is_file() else []

    def runs(self) -> List[str]:
        log = self.root / ".specify" / "stub-runs.log"
        return log.read_text(encoding="utf-8").split() if log.is_file() else []

    def remove_extension(self, ext: str) -> None:
        shutil.rmtree(self.root / ".specify" / "extensions" / ext)

    def remove_preset(self, preset: str) -> None:
        shutil.rmtree(self.root / ".specify" / "presets" / preset)


def make_project(root: Path, aligned: bool, siblings: Iterable[str] = ("scopeguard", "archiguard", "auditguard"),
                 guardians: bool = True, preset: bool = True, codeowners: bool = True) -> FakeProject:
    """aligned=True: the state after `guardians configure`; aligned=False: fresh from `bundle install` after the old
    install docs (the Guardians catalogs alone in the catalog files, the agent events not wired)."""
    siblings = tuple(siblings)
    (root / ".specify").mkdir(parents=True, exist_ok=True)
    for ext in siblings:
        ext_dir = root / ".specify" / "extensions" / ext
        (ext_dir / "scripts" / "python").mkdir(parents=True, exist_ok=True)
        events = "".join(f"  {event}:\n    command: {command}\n" for event, command in EVENTS.get(ext, []))
        (ext_dir / "extension.yml").write_text(textwrap.dedent(f"""\
            schema_version: "1.0"
            extension:
              id: {ext}
              name: "{NAMES[ext]}"
              version: "{VERSIONS[ext]}"
              description: "stub"
            requires:
              speckit_version: ">=1.0.1"
            provides:
              commands: []
            """) + (f"events:\n{events}" if events else ""), encoding="utf-8")
        shutil.copy(FIXTURES / f"{ext}-config.yml", ext_dir / f"{ext}-config.yml")
        stub = STUB.format(ext=ext, name=NAMES[ext], version=VERSIONS[ext], default_integration=DEFAULT_INTEGRATION[ext],
                           default_mode=DEFAULT_MODE[ext])
        (ext_dir / "scripts" / "python" / f"{ext}.py").write_text(stub, encoding="utf-8")
    if guardians:
        g_dir = root / ".specify" / "extensions" / "guardians"
        g_dir.mkdir(parents=True, exist_ok=True)
        (g_dir / "extension.yml").write_text('schema_version: "1.0"\nextension:\n  id: guardians\n  name: "Guardians"\n'
                                             f'  version: "{VERSIONS["guardians"]}"\n', encoding="utf-8")
    if preset:
        p_dir = root / ".specify" / "presets" / "archiguard-templates"
        p_dir.mkdir(parents=True, exist_ok=True)
        (p_dir / "preset.yml").write_text('schema_version: "1.0"\npreset:\n  id: archiguard-templates\n  version: "' + PRESET_VERSION + '"\n', encoding="utf-8")
    project = FakeProject(root)
    project.write(".specify/integration.json", json.dumps({"integration": "claude", "installed_integrations": ["claude"]}) + "\n")
    project.write(".specify/init-options.json", json.dumps({"ai": "claude", "integration": "claude", "script": "sh"}) + "\n")
    for kind in ("extension", "preset"):
        project.write(f".specify/{kind}-catalogs.yml", catalog_file(kind, seeded=aligned))
    wired = [c for ext in siblings for _event, c in EVENTS.get(ext, [])] if aligned else []
    project.write(".claude/settings.json", claude_settings(wired))
    if aligned:
        project.write(".specify/extensions.yml", registry_text(aligned_enabled, aligned_priority, siblings))
        project.write(".gitattributes", GITATTRIBUTES)
        if "scopeguard" in siblings:
            project.replace("scopeguard", "integration: inline", "integration: embedded")
        if "archiguard" in siblings:
            project.replace("archiguard", '"specs/*/gates/**/*.json"]', '"specs/*/gates/**/*.json", "audit/**", ".specify/extensions/auditguard/**"]')
    else:
        project.write(".specify/extensions.yml", registry_text(all_enabled, default_priority, siblings))
    if codeowners:
        project.write(".github/CODEOWNERS", CODEOWNERS)
    return project


@pytest.fixture
def aligned(tmp_path: Path) -> FakeProject:
    return make_project(tmp_path / "aligned", aligned=True)


@pytest.fixture
def fresh(tmp_path: Path) -> FakeProject:
    return make_project(tmp_path / "fresh", aligned=False)


@pytest.fixture
def chdir(monkeypatch):
    def _chdir(path: Path) -> None:
        monkeypatch.chdir(path)
    return _chdir


def guardians_cli(*args: str) -> Tuple[int, str]:
    """Run the Guardians CLI in-process; (exit code, stdout)."""
    import contextlib
    import io

    from guardians_core.cli import main

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(args))
    return code, out.getvalue()


def requires_bash() -> bool:
    return shutil.which("bash") is not None and os.name != "nt"
