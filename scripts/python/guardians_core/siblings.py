"""The installed Guardians as Guardians sees them: manifests, config files, launchers, `configure --dry-run --json`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import yamlio
from .common import EXTENSIONS_YML, GUARDIANS, PRESETS, SIBLINGS, GuardiansError, read_text, rel, run
from .speckit import handlers

# What the siblings assume when a key is missing from their config (their config templates, at the pins).
ARCHIGUARD_READONLY = [".specify/standards/**", ".specify/archiguard/**", ".specify/extensions/archiguard/**",
                       "specs/*/gates/**/*.json"]
ARCHIGUARD_SCOPE_RANGE = ">=0.3.0,<0.5"
AUDITGUARD_READONLY = ["audit/**", ".specify/extensions/auditguard/**"]
AUDITGUARD_COLLECTOR_RANGES = {"scopeguard": ">=0.4,<0.6", "archiguard": ">=0.1,<0.3"}
AUDITGUARD_GITATTRIBUTES = ["{audit}/**/*.jsonl -text", "{audit}/**/evidence/** -text", "{audit}/**/seal.json -text"]
DEFAULT_INTEGRATION = {"scopeguard": "inline", "archiguard": "inline", "auditguard": "hooks"}
DEFAULT_MODE = {"scopeguard": "enforce", "archiguard": "enforce", "auditguard": "record"}


class Sibling:
    def __init__(self, root: Path, ext_id: str):
        self.id = ext_id
        self.root = root
        self.dir = root / ".specify" / "extensions" / ext_id
        self.manifest = self.dir / "extension.yml"
        self.config_path = self.dir / f"{ext_id}-config.yml"
        self.launcher = self.dir / "scripts" / "python" / f"{ext_id}.py"
        self._version: Optional[str] = None
        self._config: Optional[Dict[str, Any]] = None
        self._status: Optional[Dict[str, Any]] = None
        self._status_done = False
        self.status_error = ""

    @property
    def installed(self) -> bool:
        return self.manifest.is_file()

    @property
    def version(self) -> Optional[str]:
        if not self.installed:
            return None
        if self._version is None:
            try:
                self._version = str(yamlio.get(yamlio.load_file(self.manifest), "extension", "version", default="?"))
            except GuardiansError:
                self._version = "?"
        return self._version

    def event_handlers(self) -> List[Tuple[str, str]]:
        """(event, command) of the agent events its manifest declares (`events:`), which Spec Kit wires into the agent."""
        try:
            events = yamlio.get(yamlio.load_file(self.manifest), "events", default={}) if self.installed else {}
        except GuardiansError:
            return []
        if not isinstance(events, dict):
            return []
        return [(str(event), str(h["command"])) for event, raw in events.items() for h in handlers(raw) if h.get("command")]

    def config(self) -> Dict[str, Any]:
        """The committed config file (not the workstation overrides - those show in status())."""
        if self._config is None:
            self._config = yamlio.load_file(self.config_path) if self.config_path.is_file() else {}
        return self._config

    def get(self, *keys: str, default: Any = None) -> Any:
        return yamlio.get(self.config(), *keys, default=default)

    def config_hint(self) -> str:
        """How to create a missing config file: copy the template the manifest declares for it, as Spec Kit does when
        it installs the extension (a bundle install before Spec Kit 1.0.3 skipped that step)."""
        template = "config-template.yml"
        try:
            for entry in yamlio.get(yamlio.load_file(self.manifest), "provides", "config", default=[]) or []:
                if isinstance(entry, dict) and entry.get("name") == self.config_path.name and entry.get("template"):
                    template = str(entry["template"])
        except GuardiansError:
            pass
        return f"copy {rel(self.dir / template, self.root)} to {rel(self.config_path, self.root)}"

    def status(self) -> Optional[Dict[str, Any]]:
        """The sibling's own `configure --dry-run --json`: integration after its overrides and fallbacks, hooks, ..."""
        if self._status_done:
            return self._status
        self._status_done = True
        if not self.launcher.is_file():
            self.status_error = f"{self.launcher.relative_to(self.root).as_posix()} not found"
            return None
        code, out, err = run([sys.executable, str(self.launcher), "configure", "--dry-run", "--json"], self.root)
        if code != 0:
            self.status_error = f"configure --dry-run exited {code}: {(err or out).strip().splitlines()[-1:] or ['']}"[:300]
            return None
        try:
            start = out.index("{")
            self._status = json.loads(out[start:])
        except (ValueError, json.JSONDecodeError) as exc:
            self.status_error = f"configure --dry-run --json did not print JSON ({exc})"
            return None
        return self._status

    def configure(self, dry_run: bool) -> Tuple[int, str]:
        """Run the sibling's own configure; (exit code, combined output)."""
        if not self.launcher.is_file():
            return 2, f"{self.id}: launcher not found at {self.launcher}"
        cmd = [sys.executable, str(self.launcher), "configure"] + (["--dry-run"] if dry_run else [])
        code, out, err = run(cmd, self.root, timeout=300)
        text = out + (("\n" + err) if err.strip() else "")
        return code, text.strip()

    def reset(self) -> None:
        self._config = None
        self._status = None
        self._status_done = False
        self.status_error = ""

    # ----- derived settings with the siblings' defaults ------------------------------------------------

    def integration(self) -> str:
        """Configured integration (status first - it includes local overrides - then the file, then the default)."""
        status = self.status()
        if status and status.get("integration"):
            return str(status["integration"])
        return str(self.get("integration", default=DEFAULT_INTEGRATION.get(self.id, "?")))

    def effective_integration(self) -> str:
        status = self.status()
        if status and status.get("effective_integration"):
            return str(status["effective_integration"])
        return self.integration()

    def mode(self) -> str:
        status = self.status()
        if status and status.get("mode"):
            return str(status["mode"])
        return str(self.get("mode", default=DEFAULT_MODE.get(self.id, "?")))

    def scope_in_pipeline(self) -> Optional[bool]:
        """archiGuard: whether its pipeline runs the scope gate (None when unknown)."""
        status = self.status()
        if status is None or "scope_in_pipeline" not in status:
            return None
        return bool(status["scope_in_pipeline"])

    def audit_root(self) -> str:
        return str(self.get("audit", "root", default="audit")).strip("/") or "audit"

    def audit_readonly(self) -> List[str]:
        """auditGuard's read-only paths (what archiGuard's edit guard must cover too)."""
        configured = self.get("guard", "readonly")
        if isinstance(configured, list) and configured:
            return [str(p) for p in configured]
        root = self.audit_root()
        return [p.replace("audit/", f"{root}/", 1) if p.startswith("audit/") else p for p in AUDITGUARD_READONLY]


class Project:
    """Everything verify and configure look at, read once."""

    def __init__(self, root: Path):
        self.root = root
        yamlio.set_search_root(root)
        self.siblings: Dict[str, Sibling] = {ext: Sibling(root, ext) for ext in GUARDIANS}
        self._registry: Optional[Dict[str, Any]] = None

    def sibling(self, ext_id: str) -> Sibling:
        return self.siblings[ext_id]

    @property
    def installed(self) -> List[str]:
        return [ext for ext in GUARDIANS if self.siblings[ext].installed]

    def extension_enabled(self, ext_id: str) -> bool:
        """Spec Kit's registry flag (`specify extension disable` clears it); an extension it does not track counts as
        enabled, as Spec Kit's event refresh counts it."""
        data = None
        path = self.root / ".specify" / "extensions" / ".registry"
        if path.is_file():
            try:
                data = json.loads(read_text(path))
            except (OSError, ValueError):
                data = None
        entry = data.get("extensions", {}).get(ext_id) if isinstance(data, dict) and isinstance(data.get("extensions"), dict) else None
        return not (isinstance(entry, dict) and entry.get("enabled") is False)

    def declared_events(self) -> Dict[str, List[Tuple[str, str]]]:
        """Installed, enabled Guardians -> (event, command) of their agent events (archiGuard and auditGuard declare some)."""
        out: Dict[str, List[Tuple[str, str]]] = {}
        for ext in SIBLINGS:
            sib = self.sibling(ext)
            pairs = sib.event_handlers() if sib.installed and self.extension_enabled(ext) else []
            if pairs:
                out[ext] = pairs
        return out

    def preset_installed(self, preset_id: str) -> bool:
        return (self.root / ".specify" / "presets" / preset_id).is_dir()

    def preset_of(self, ext_id: str) -> str:
        return PRESETS[ext_id]

    @property
    def registry_path(self) -> Path:
        return self.root / EXTENSIONS_YML

    def registry(self) -> Dict[str, Any]:
        if self._registry is None:
            self._registry = yamlio.load_file(self.registry_path) if self.registry_path.is_file() else {}
        return self._registry

    def hooks(self) -> Dict[str, List[Dict[str, Any]]]:
        """event -> entries (dicts) of the hook registry."""
        out: Dict[str, List[Dict[str, Any]]] = {}
        for event, entries in (self.registry().get("hooks") or {}).items():
            if isinstance(entries, dict):
                entries = [entries]
            out[str(event)] = [e for e in (entries or []) if isinstance(e, dict)]
        return out

    def hook_counts(self, ext_id: str) -> Tuple[int, int]:
        """(enabled, registered) hook entries of an extension."""
        enabled = registered = 0
        for entries in self.hooks().values():
            for entry in entries:
                if entry.get("extension") == ext_id:
                    registered += 1
                    enabled += 1 if entry.get("enabled", True) else 0
        return enabled, registered

    def reset(self) -> None:
        self._registry = None
        for sibling in self.siblings.values():
            sibling.reset()

    def read(self, relative: str) -> Optional[str]:
        path = self.root / relative
        return read_text(path) if path.is_file() else None

    def codeowners(self) -> Optional[Path]:
        for candidate in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
            if (self.root / candidate).is_file():
                return self.root / candidate
        return None


def siblings_only(project: Project) -> List[Sibling]:
    return [project.sibling(ext) for ext in SIBLINGS]
