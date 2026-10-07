"""Test fixtures: a fake Spec Kit project with the three siblings (their real config templates at the pinned
versions, stub launchers that answer `configure --dry-run --json` the way the real ones do), the preset, a hook
registry in Spec Kit's own dump style, and Guardians itself."""

from __future__ import annotations

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

    def runs(self) -> List[str]:
        log = self.root / ".specify" / "stub-runs.log"
        return log.read_text(encoding="utf-8").split() if log.is_file() else []

    def remove_extension(self, ext: str) -> None:
        shutil.rmtree(self.root / ".specify" / "extensions" / ext)

    def remove_preset(self, preset: str) -> None:
        shutil.rmtree(self.root / ".specify" / "presets" / preset)


def make_project(root: Path, aligned: bool, siblings: Iterable[str] = ("scopeguard", "archiguard", "auditguard"),
                 guardians: bool = True, preset: bool = True, codeowners: bool = True) -> FakeProject:
    """aligned=True: the state after `guardians configure`; aligned=False: fresh from `bundle install`."""
    (root / ".specify").mkdir(parents=True, exist_ok=True)
    for ext in siblings:
        ext_dir = root / ".specify" / "extensions" / ext
        (ext_dir / "scripts" / "python").mkdir(parents=True, exist_ok=True)
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
            """), encoding="utf-8")
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
