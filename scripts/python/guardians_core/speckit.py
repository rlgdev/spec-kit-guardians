"""Spec Kit's own project files that decide whether the Guardians work next to other extensions (Spec Kit 1.1.1).

- Catalog stacks. A project `.specify/extension-catalogs.yml` (`preset-catalogs.yml`) replaces the catalogs Spec Kit
  uses otherwise: the user-level file in ~/.specify/, else its built-in default and community catalogs. It never
  merges. A file that lists only the family's catalogs (what `specify extension catalog add <family catalog>` creates
  in a fresh project) hides every other extension from `specify extension search`, `info` and `update`.
- Agent events. `specify extension add` and `enable` wire the extensions' `events:` into the agent's own settings;
  `specify bundle install` does not. Without them archiGuard's edit guard and auditGuard's session, stop and guard
  events never run.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import yamlio
from .common import GuardiansError, join_lines, read_text, rel, split_lines

SPECKIT_RAW = "https://raw.githubusercontent.com/github/spec-kit/main"
# the family's catalogs: the bundle's, and each sibling's own (their READMEs' "install through a catalog")
FAMILY_CATALOG = re.compile(r"^https://raw\.githubusercontent\.com/rlgdev/spec-kit-(?:guardians|scopeguard|archiguard|auditguard)/")

# kind -> the stack file (in .specify/ and ~/.specify/), the variable that replaces the whole stack, the CLI group,
# and Spec Kit's built-in catalogs as the install docs add them back: (name, url, priority, install allowed).
# community gets priority 20 so a trusted family catalog (10) wins if one of its ids ever appears there.
CATALOGS: Dict[str, Dict[str, Any]] = {
    "extension": {"file": "extension-catalogs.yml", "env": "SPECKIT_CATALOG_URL", "cli": "specify extension catalog add",
                  "builtin": [("default", f"{SPECKIT_RAW}/extensions/catalog.json", 1, True),
                              ("community", f"{SPECKIT_RAW}/extensions/catalog.community.json", 20, False)]},
    "preset": {"file": "preset-catalogs.yml", "env": "SPECKIT_PRESET_CATALOG_URL", "cli": "specify preset catalog add",
               "builtin": [("default", f"{SPECKIT_RAW}/presets/catalog.json", 1, True),
                           ("community", f"{SPECKIT_RAW}/presets/catalog.community.json", 20, False)]},
}

# The integrations Spec Kit 1.1.1 wires agent events for (`supports_events()`), and the file its event refresh
# writes the event commands into. Another integration gets no agent events from Spec Kit.
EVENT_FILES: Dict[str, str] = {
    "claude": ".claude/settings.json",
    "codex": ".codex/config.toml",
    "copilot": ".github/hooks/speckit.json",
    "cursor-agent": ".cursor/hooks.json",
    "devin": ".devin/hooks.v1.json",
    "gemini": ".gemini/settings.json",
    "opencode": ".opencode/plugin/speckit-events.ts",
    "qwen": ".qwen/settings.json",
    "tabnine": ".tabnine/agent/settings.json",
    "vibe": ".vibe/hooks.toml",
}
EVENTS_OVERRIDE = Path(".specify") / "integration-events.yml"
WIRE_EVENTS = "specify extension disable guardians && specify extension enable guardians"
_OFF = ("false", "0", "no", "off")


def _json(path: Path) -> Optional[Any]:
    try:
        return json.loads(read_text(path))
    except (OSError, ValueError):
        return None


def specify_command() -> Optional[List[str]]:
    """The Spec Kit CLI on PATH, as the start of a command line (tests replace this function)."""
    found = shutil.which("specify")
    return [found] if found else None


def init_ai(root: Path) -> str:
    data = _json(root / ".specify" / "init-options.json")
    return str(data.get("ai") or "") if isinstance(data, dict) else ""


# --------------------------------------------------------------------------- #
# catalog stacks                                                                #
# --------------------------------------------------------------------------- #

class CatalogStack:
    """One kind's catalog stack as Spec Kit resolves it, seen from the project file."""

    def __init__(self, root: Path, kind: str):
        spec = CATALOGS[kind]
        self.root = root
        self.kind = kind
        self.path = root / ".specify" / spec["file"]
        self.user_path = Path.home() / ".specify" / spec["file"]
        self.env = spec["env"] if os.environ.get(spec["env"], "").strip() else ""
        self.entries: Optional[List[Dict[str, Any]]] = None   # None: no project stack in force
        self.empty = False                                     # an extension file with no catalog: Spec Kit fails
        self.error = ""
        if self.path.is_file():
            self.entries, self.empty, self.error = _stack_entries(self.path, kind)

    @property
    def label(self) -> str:
        return rel(self.path, self.root)

    @property
    def urls(self) -> List[str]:
        return [str(e.get("url")).strip() for e in self.entries or []]

    def replaced(self) -> List[Tuple[str, str]]:
        """(name, url) of the catalogs Spec Kit would use without the project file: the user's, else its own."""
        if self.user_path.is_file():
            entries, _empty, error = _stack_entries(self.user_path, self.kind)
            if entries and not error:
                return [(str(e.get("name") or f"catalog-{i + 1}"), str(e.get("url")).strip()) for i, e in enumerate(entries)]
        return [(name, url) for name, url, _p, _a in CATALOGS[self.kind]["builtin"]]

    def hidden(self) -> List[Tuple[str, str]]:
        """The catalogs the project file hides (empty when no project stack is in force)."""
        if self.env or self.error or self.entries is None:
            return []
        have = set(self.urls)
        return [(name, url) for name, url in self.replaced() if url not in have]

    def family_only(self) -> bool:
        return bool(self.entries) and all(FAMILY_CATALOG.match(url) for url in self.urls)

    def repairable(self) -> bool:
        """guardians configure adds Spec Kit's catalogs back only to a file it can tell the family's docs created:
        every entry a family catalog, and no user-level file (whose entries it would not copy into the project)."""
        return bool(self.hidden()) and bool(self.builtin_to_add()) and self.family_only() and not self.user_path.is_file()

    def builtin_to_add(self) -> List[Tuple[str, str, int, bool]]:
        have = set(self.urls)
        names = {str(e.get("name")) for e in self.entries or []}
        return [c for c in CATALOGS[self.kind]["builtin"] if c[1] not in have and c[0] not in names]

    def add_commands(self) -> str:
        cli = CATALOGS[self.kind]["cli"]
        return " / ".join(f"{cli} {url} --name {name} --priority {prio} --{'' if allowed else 'no-'}install-allowed"
                          for name, url, prio, allowed in self.builtin_to_add())


def _stack_entries(path: Path, kind: str) -> Tuple[Optional[List[Dict[str, Any]]], bool, str]:
    """(entries with a url or None when the file puts no stack in force, empty, error) - Spec Kit's reading rules."""
    try:
        data = yamlio.loads(read_text(path), str(path))
    except (GuardiansError, OSError, UnicodeError) as exc:
        return None, False, str(exc)
    if data is None:
        if kind == "preset":
            return None, False, ""     # presets: an empty file is no stack; extensions: Spec Kit reads it as {}
        data = {}
    if not isinstance(data, dict):
        return None, False, f"{path.name}: expected a mapping at the top level"
    items = data.get("catalogs")
    if items is None and kind == "preset":
        return None, False, ""
    if items is None:
        items = []
    if not isinstance(items, list):
        return None, False, f"{path.name}: 'catalogs' must be a list"
    if any(not isinstance(item, dict) for item in items):
        return None, False, f"{path.name}: every catalog entry must be a mapping"
    entries = [item for item in items if str(item.get("url", "")).strip()]
    if not entries:
        return (None, False, "") if kind == "preset" else ([], True, "")
    return entries, False, ""


def append_catalogs(text: str, catalogs: List[Tuple[str, str, int, bool]]) -> Optional[str]:
    """Append entries to the block list under `catalogs:`, in the shape `specify ... catalog add` writes them (so a
    later run of that command for the same catalog is a no-op). None when the file has another shape."""
    lines, eol = split_lines(text)
    start = next((i for i, line in enumerate(lines) if re.match(r"^catalogs:\s*(#.*)?$", line)), None)
    if start is None:
        return None
    last, pad = start, None
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not lines[j].startswith((" ", "-")):
            break
        item = re.match(r"^(\s*)-\s", lines[j])
        if item and pad is None:
            pad = item.group(1)
        last = j
    if pad is None:
        return None
    new: List[str] = []
    for name, url, priority, allowed in catalogs:
        new += [f"{pad}- name: {name}", f"{pad}  url: {url}", f"{pad}  priority: {priority}",
                f"{pad}  install_allowed: {'true' if allowed else 'false'}", f"{pad}  description: ''"]
    lines[last + 1:last + 1] = new
    return join_lines(lines, eol)


# --------------------------------------------------------------------------- #
# agent events                                                                  #
# --------------------------------------------------------------------------- #

class IntegrationEvents:
    """Whether the declared agent events of the installed Guardians are wired for one integration."""

    def __init__(self, key: str, file: Optional[str], state: str, missing: Optional[List[str]] = None):
        self.key = key
        self.file = file
        self.state = state          # wired | missing | off | override | unsupported
        self.missing = missing or []


def installed_integrations(root: Path) -> Tuple[List[str], Dict[str, Any]]:
    data = _json(root / ".specify" / "integration.json")
    if not isinstance(data, dict):
        return [], {}
    keys = data.get("installed_integrations")
    if not isinstance(keys, list) or not keys:
        keys = [data["integration"]] if data.get("integration") else []
    return [str(k) for k in keys], data


def _events_off(state: Dict[str, Any], key: str) -> bool:
    """`specify init/integration ... --integration-options "--events false"` stored for this integration."""
    setting = (state.get("integration_settings") or {}).get(key) if isinstance(state.get("integration_settings"), dict) else None
    if not isinstance(setting, dict):
        return False
    parsed = setting.get("parsed_options")
    if isinstance(parsed, dict) and "events" in parsed:
        return str(parsed["events"]).strip().lower() in _OFF
    raw = setting.get("raw_options")
    return bool(isinstance(raw, str) and re.search(r"--events[=\s]+[\"']?(false|0|no|off)\b", raw, re.I))


def _override_keys(root: Path) -> List[str]:
    """Integrations whose events `.specify/integration-events.yml` sets itself (Spec Kit then uses that set)."""
    path = root / EVENTS_OVERRIDE
    if not path.is_file():
        return []
    try:
        data = yamlio.loads(read_text(path), str(path))
    except GuardiansError:
        return []
    integrations = data.get("integrations") if isinstance(data, dict) else None
    if not isinstance(integrations, dict):
        return []
    return [str(k) for k, v in integrations.items() if isinstance(v, dict) and "events" in v]


def event_wiring(root: Path, declared: Dict[str, List[str]]) -> List[IntegrationEvents]:
    """One entry per installed integration. `declared`: extension id -> its event commands (enabled Guardians only)."""
    keys, state = installed_integrations(root)
    overrides = _override_keys(root)
    out: List[IntegrationEvents] = []
    for key in keys:
        file = EVENT_FILES.get(key)
        if file is None:
            out.append(IntegrationEvents(key, None, "unsupported"))
        elif _events_off(state, key):
            out.append(IntegrationEvents(key, file, "off"))
        elif key in overrides:
            out.append(IntegrationEvents(key, file, "override"))
        else:
            path = root / file
            try:
                text = read_text(path) if path.is_file() else ""
            except (OSError, UnicodeError):
                text = ""
            missing = [ext for ext, commands in declared.items() if not any(c in text for c in commands)]
            out.append(IntegrationEvents(key, file, "missing" if missing else "wired", missing))
    return out
