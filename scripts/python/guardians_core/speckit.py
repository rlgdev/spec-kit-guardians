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
from urllib.parse import urlparse

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
# the canonical events Spec Kit 1.1.1 has no native event for in these integrations (it writes nothing for them)
UNSUPPORTED_EVENTS: Dict[str, Tuple[str, ...]] = {"opencode": ("stop",), "vibe": ("session_start", "session_end")}
EVENTS_OVERRIDE = Path(".specify") / "integration-events.yml"
WIRE_EVENTS = "specify extension disable guardians, then specify extension enable guardians"
_OFF = ("false", "0", "no", "off")
CANONICAL_EVENTS = ("session_start", "pre_tool_use", "post_tool_use", "session_end", "user_prompt_submit", "stop")


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

Catalog = Tuple[str, str, int, bool]   # name, url, priority, install allowed


_SPECKIT_REF = re.compile(r"^https://raw\.githubusercontent\.com/github/spec-kit/[^/]+/")


def _same_catalog(a: str, b: str) -> bool:
    """The same catalog; Spec Kit's own at another tag or branch (`.../spec-kit/v1.1.1/...`) counts as the same."""
    return a == b or (bool(_SPECKIT_REF.match(a)) and _SPECKIT_REF.sub("", a) == _SPECKIT_REF.sub("", b)
                      and bool(_SPECKIT_REF.match(b)))


def _allowed(value: Any) -> bool:
    """`install_allowed` the way Spec Kit reads it: a string counts when it is true / yes / 1."""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def _url_error(url: str) -> str:
    """Spec Kit's catalog URL rule: https, or http on localhost; a host."""
    try:
        parsed = urlparse(url)
        _ = parsed.port
    except ValueError:
        return f"catalog URL is malformed: {url}"
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        return f"catalog URL must use HTTPS: {url}"
    return "" if parsed.hostname else f"catalog URL has no host: {url}"


class CatalogStack:
    """One kind's catalog stack as Spec Kit resolves it, seen from the project file."""

    def __init__(self, root: Path, kind: str):
        spec = CATALOGS[kind]
        self.root = root
        self.kind = kind
        self.path = root / ".specify" / spec["file"]
        self.user_path = Path.home() / ".specify" / spec["file"]
        self.env = spec["env"] if os.environ.get(spec["env"]) else ""   # Spec Kit: any non-empty value
        self.entries: Optional[List[Dict[str, Any]]] = None   # None: no project stack in force
        self.empty = False                                     # an extension file with no catalog: Spec Kit fails
        self.error = ""
        if self.path.is_file():
            self.entries, self.empty, self.error = _stack_entries(self.path, kind)

    @property
    def label(self) -> str:
        return rel(self.path, self.root)

    @property
    def ignored(self) -> bool:
        """A preset file that puts no stack in force (no catalog in it): Spec Kit uses the next one."""
        return self.path.is_file() and self.entries is None and not self.error

    @property
    def urls(self) -> List[str]:
        return [str(e.get("url")).strip() for e in self.entries or []]

    def replaced(self) -> List[Catalog]:
        """The catalogs Spec Kit would use without the project file: the user-level file's, else its own."""
        if self.user_path.is_file():
            entries, _empty, error = _stack_entries(self.user_path, self.kind)
            if entries and not error:
                return [(str(e.get("name") or f"catalog-{i + 1}"), str(e.get("url")).strip(), _priority(e, i),
                         _allowed(e.get("install_allowed", False))) for i, e in enumerate(entries)]
        return list(CATALOGS[self.kind]["builtin"])

    def _in_force(self) -> bool:
        """A project stack to judge. With SPECKIT_*CATALOG_URL set Spec Kit ignores the file on this machine only; it is
        judged all the same, as it is in force for everyone without the variable (CI, the rest of the team)."""
        return not (self.error or self.entries is None)

    def _entry_for(self, url: str) -> Optional[Dict[str, Any]]:
        return next((e for e in self.entries or [] if _same_catalog(str(e.get("url")).strip(), url)), None)

    def hidden(self) -> List[Catalog]:
        """The catalogs the project file hides."""
        if not self._in_force():
            return []
        return [c for c in self.replaced() if self._entry_for(c[1]) is None]

    def restricted(self) -> List[Tuple[Catalog, str]]:
        """Replaced install-allowed catalogs the project file lists as discovery-only: Spec Kit then refuses to
        install or update their extensions from them. (catalog, the project entry's name)"""
        if not self._in_force():
            return []
        out = []
        for catalog in self.replaced():
            entry = self._entry_for(catalog[1])
            if catalog[3] and entry is not None and not _allowed(entry.get("install_allowed", False)):
                out.append((catalog, str(entry.get("name") or catalog[0])))
        return out

    def family_only(self) -> bool:
        return bool(self.entries) and all(FAMILY_CATALOG.match(url) for url in self.urls)

    def repairable(self) -> bool:
        """guardians configure adds Spec Kit's catalogs back only to a file it can tell the family's docs created:
        every entry a family catalog, and no user-level file (whose entries it would not copy into the project)."""
        return bool(self.hidden()) and bool(self.builtin_to_add()) and self.family_only() and not self.user_path.is_file()

    def builtin_to_add(self) -> List[Catalog]:
        names = {str(e.get("name")) for e in self.entries or []}
        return [c for c in CATALOGS[self.kind]["builtin"] if self._entry_for(c[1]) is None and c[0] not in names]

    def add_command(self, catalog: Catalog) -> str:
        name, url, prio, allowed = catalog
        return f"{CATALOGS[self.kind]['cli']} {url} --name {name} --priority {prio} --{'' if allowed else 'no-'}install-allowed"

    def add_commands(self) -> str:
        return " / ".join(self.add_command(c) for c in self.builtin_to_add())


def _priority(entry: Dict[str, Any], index: int) -> int:
    try:
        return int(entry.get("priority", index + 1))
    except (TypeError, ValueError, OverflowError):
        return index + 1


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
    for index, entry in enumerate(entries):
        problem = _url_error(str(entry.get("url")).strip())
        priority = entry.get("priority", index + 1)
        if not problem:
            try:
                if isinstance(priority, bool):
                    raise TypeError
                int(priority)                     # Spec Kit's own test
            except (TypeError, ValueError, OverflowError):
                problem = f"catalog {entry.get('name', index + 1)!r}: priority must be an integer, got {priority!r}"
        if problem:
            return None, False, f"{path.name}: {problem} (Spec Kit refuses the file)"
    if not entries:
        return (None, False, "") if kind == "preset" else ([], True, "")
    return entries, False, ""


def append_catalogs(text: str, catalogs: List[Catalog]) -> Optional[str]:
    """Append entries to the block list under `catalogs:`, in the shape `specify ... catalog add` writes them (Spec
    Kit 1.1 then takes a later `catalog add` of the same catalog as a no-op). None when the file has another shape."""
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    lines, eol = split_lines(text[len(bom):])
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
    return bom + join_lines(lines, eol)


# --------------------------------------------------------------------------- #
# agent events                                                                  #
# --------------------------------------------------------------------------- #

class IntegrationEvents:
    """Whether the declared agent events of the installed Guardians are wired for one integration."""

    def __init__(self, key: str, file: Optional[str], state: str, missing: Optional[List[str]] = None,
                 unreadable: bool = False):
        self.key = key
        self.file = file
        self.state = state          # wired | missing | off | override | unsupported
        self.missing = missing or []
        self.unreadable = unreadable  # a JSON settings file that does not parse (comments): Spec Kit cannot merge into it


def handlers(value: Any) -> List[Dict[str, Any]]:
    """An event's handlers in either shape Spec Kit accepts: one mapping or a list of them."""
    if isinstance(value, dict):
        value = [value]
    return [h for h in value if isinstance(h, dict)] if isinstance(value, list) else []


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


def _override_valid(events: Dict[str, Any]) -> bool:
    """Spec Kit adopts an override only when every entry is valid (an explicit `events: {}` included)."""
    for event, raw in events.items():
        found = handlers(raw)
        if not found or event not in CANONICAL_EVENTS:
            return False
        for handler in found:
            command, matcher, timeout = handler.get("command"), handler.get("matcher"), handler.get("timeout")
            if not isinstance(command, str) or not command.strip():
                return False
            if matcher is not None and not isinstance(matcher, str):
                return False
            if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0):
                return False
    return True


def _override_keys(root: Path) -> List[str]:
    """Integrations whose events `.specify/integration-events.yml` sets itself, by Spec Kit's rules: a mapping entry
    whose `events` (absent = none) is a mapping of valid entries replaces the events; anything else is ignored."""
    path = root / EVENTS_OVERRIDE
    if not path.is_file():
        return []
    try:
        data = yamlio.loads(read_text(path), str(path))
    except (GuardiansError, OSError, UnicodeError):
        return []
    integrations = data.get("integrations") if isinstance(data, dict) else None
    if not isinstance(integrations, dict):
        return []
    out = []
    for key, value in integrations.items():
        events = value.get("events") if isinstance(value, dict) else None
        if isinstance(value, dict) and (events is None or (isinstance(events, dict) and _override_valid(events))):
            out.append(str(key))
    return out


def event_wiring(root: Path, declared: Dict[str, List[Tuple[str, str]]]) -> List[IntegrationEvents]:
    """One entry per installed integration. `declared`: extension id -> its (event, command) pairs (enabled Guardians
    only). Wired means: each command appears in the settings file at least once per declared event the integration
    has a native event for (archiGuard's edit guard runs before and after a tool, so twice)."""
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
            skip = UNSUPPORTED_EVENTS.get(key, ())
            missing = []
            for ext, pairs in declared.items():
                wanted: Dict[str, int] = {}
                for event, command in pairs:
                    if event not in skip:
                        wanted[command] = wanted.get(command, 0) + 1
                if any(len(re.findall(re.escape(c) + r"(?![\w.-])", text)) < n for c, n in wanted.items()):
                    missing.append(ext)
            unreadable = False
            if missing and file.endswith(".json") and text.strip():
                try:
                    json.loads(text)
                except ValueError:
                    unreadable = True
            out.append(IntegrationEvents(key, file, "missing" if missing else "wired", missing, unreadable))
    return out


def toggle_blocker(root: Path, guardians_installed: bool, guardians_enabled: bool) -> str:
    """Why guardians configure does not run WIRE_EVENTS itself here ('' when it does)."""
    if not guardians_installed:
        return "Guardians is not installed in this project"
    if not guardians_enabled:
        return "Guardians is disabled in Spec Kit"
    if init_ai(root) == "generic":
        return "the generic integration: Spec Kit then rewrites every enabled extension's generic commands"
    if specify_command() is None:
        return "specify is not on PATH"
    return ""
