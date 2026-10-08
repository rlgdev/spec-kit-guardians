"""guardians-config.yml: optional; defaults apply when absent; unknown keys are errors."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import yamlio
from .common import SIBLINGS, GuardiansError

CHECKS = (
    "installed", "catalogs_keep_defaults", "preset_matches_integration", "versions_in_range", "scopeguard_embedded",
    "auditguard_integration", "hook_order", "hooks_match_integration", "git_base_agrees",
    "edit_guard_covers_audit", "agent_events_wired", "modes_agree", "gitattributes", "codeowners",
)
SEVERITIES = ("fail", "warn", "off")

DEFAULTS: Dict[str, Any] = {
    "version": 1,
    "order": list(SIBLINGS),
    "hook_priority": {"auditguard": {"before": 1, "after": 90}, "default": 10},
    "checks": {
        "installed": "fail",
        "catalogs_keep_defaults": "warn",
        "preset_matches_integration": "fail",
        "versions_in_range": "fail",
        "scopeguard_embedded": "fail",
        "auditguard_integration": "warn",
        "hook_order": "fail",
        "hooks_match_integration": "warn",
        "git_base_agrees": "fail",
        "edit_guard_covers_audit": "fail",
        "agent_events_wired": "warn",
        "modes_agree": "warn",
        "gitattributes": "warn",
        "codeowners": "warn",
    },
}


class Config:
    def __init__(self, data: Dict[str, Any], path: Optional[Path]):
        self.data = data
        self.path = path

    @property
    def order(self) -> List[str]:
        return list(self.data["order"])

    def priority(self, extension: str, event: str, current: Optional[int]) -> Optional[int]:
        """The wanted hook priority for a Guardian's entry; None = leave the entry as it is."""
        hp = self.data["hook_priority"]
        if extension == "auditguard":
            return int(hp["auditguard"]["before"] if event.startswith("before_") else hp["auditguard"]["after"])
        if extension in SIBLINGS:
            return None if current is not None else int(hp["default"])
        return None

    def severity(self, check: str) -> str:
        return str(self.data["checks"].get(check, "fail"))


def _int_at_least_one(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GuardiansError(f"{where}: must be an integer >= 1, got {value!r}")
    return value


def load_config(root: Path, explicit: Optional[Path] = None) -> Config:
    path = explicit or (root / ".specify" / "extensions" / "guardians" / "guardians-config.yml")
    data = copy.deepcopy(DEFAULTS)
    if not path.is_file():
        if explicit:
            raise GuardiansError(f"{path}: not found")
        return Config(data, None)
    raw = yamlio.load_file(path)
    where = str(path)
    unknown = sorted(set(raw) - set(DEFAULTS))
    if unknown:
        raise GuardiansError(f"{where}: unknown key(s) {', '.join(unknown)} (allowed: {', '.join(DEFAULTS)})")
    if "version" in raw and raw["version"] != 1:
        raise GuardiansError(f"{where}: version must be 1")
    if "order" in raw:
        order = raw["order"]
        if not isinstance(order, list) or not order or any(o not in SIBLINGS for o in order) or len(set(order)) != len(order):
            raise GuardiansError(f"{where}: order must list each of {', '.join(SIBLINGS)} at most once")
        data["order"] = [str(o) for o in order]
    if "hook_priority" in raw:
        hp = raw["hook_priority"] or {}
        if not isinstance(hp, dict) or set(hp) - {"auditguard", "default"}:
            raise GuardiansError(f"{where}: hook_priority allows the keys auditguard and default")
        if "default" in hp:
            data["hook_priority"]["default"] = _int_at_least_one(hp["default"], f"{where}: hook_priority.default")
        if "auditguard" in hp:
            ag = hp["auditguard"] or {}
            if not isinstance(ag, dict) or set(ag) - {"before", "after"}:
                raise GuardiansError(f"{where}: hook_priority.auditguard allows the keys before and after")
            for key in ("before", "after"):
                if key in ag:
                    data["hook_priority"]["auditguard"][key] = _int_at_least_one(ag[key], f"{where}: hook_priority.auditguard.{key}")
    if "checks" in raw:
        checks = raw["checks"] or {}
        if not isinstance(checks, dict):
            raise GuardiansError(f"{where}: checks must be a mapping of check id -> fail | warn | off")
        bad = sorted(set(checks) - set(CHECKS))
        if bad:
            raise GuardiansError(f"{where}: unknown check(s) {', '.join(bad)} (known: {', '.join(CHECKS)})")
        for check, severity in checks.items():
            if severity is False:
                severity = "off"   # YAML 1.1 reads a bare `off` as false
            if severity not in SEVERITIES:
                raise GuardiansError(f"{where}: checks.{check} must be one of {', '.join(SEVERITIES)}, got {severity!r}")
            data["checks"][check] = severity
    return Config(data, path)
