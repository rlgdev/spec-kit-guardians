#!/usr/bin/env python3
"""Consistency check across the four Guardians repositories.

    python tools/check-family.py                       # siblings as ../spec-kit-<id> next to this checkout
    python tools/check-family.py --scopeguard-src DIR --archiguard-src DIR --auditguard-src DIR
    SCOPEGUARD_SRC=... ARCHIGUARD_SRC=... AUDITGUARD_SRC=... python tools/check-family.py

What must agree (one [OK] / [FAIL] line each; exit 1 on a failure, 2 when a repository is missing):
  pins        every bundle pin equals the sibling's own extension.yml version; the preset pin its preset.yml version
  catalogs    every entry of catalog/*.json equals the sibling's own catalog entry (version, download_url, provides, requires)
  ci-refs     the siblings' CI pins (SCOPEGUARD_TAG, ARCHIGUARD_TAG) and the Guardians *_REF values equal the bundle pins
  ranges      archiGuard's gates.scope.version and auditGuard's collectors.*.version accept the pinned versions, and the
              constants Guardians assumes for them (guardians_core/siblings.py) equal the siblings' templates
  fixtures    tests/fixtures/<id>-config.yml is the sibling's config-template.yml AT THE PINNED TAG (read with
              `git show v<pin>:config-template.yml` when the checkout has that tag, else its working tree)
  readonly    the read-only paths Guardians assumes equal the siblings' templates
  launchers   the bash and PowerShell launchers of all four carry the family's interpreter search (Windows Store stub guard)
  speckit     the bundle's speckit_version floor is at least every sibling's
  readmes     every sibling README and preset README names its own current release in releases/download/v<version>/
Reads YAML with PyYAML when importable, else with the auditGuard checkout's reader.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts" / "python"))
from guardians_core.common import version_satisfies  # noqa: E402
from guardians_core.siblings import (ARCHIGUARD_READONLY, ARCHIGUARD_SCOPE_RANGE, AUDITGUARD_COLLECTOR_RANGES,  # noqa: E402
                                     AUDITGUARD_READONLY)

SIBLINGS = ("scopeguard", "archiguard", "auditguard")
NAMES = {"scopeguard": "scopeGuard", "archiguard": "archiGuard", "auditguard": "auditGuard", "guardians": "Guardians"}
CATALOG_KEYS = ("version", "download_url", "provides", "requires", "repository", "license")


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def ok(self, check: str, message: str) -> None:
        print(f"[OK]   {check:<10} {message}")

    def fail(self, check: str, message: str) -> None:
        self.failed += 1
        print(f"[FAIL] {check:<10} {message}")

    def result(self, check: str, problems: List[str], good: str) -> None:
        if problems:
            for problem in problems:
                self.fail(check, problem)
        else:
            self.ok(check, good)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def yaml_loader(auditguard: Path):
    try:
        import yaml  # type: ignore

        return lambda text: yaml.safe_load(text)
    except ImportError:
        sys.path.insert(0, str(auditguard / "scripts" / "python"))
        from auditguard_core import yamlio  # type: ignore

        return lambda text: yamlio.loads(text, "<yaml>")


def manifest_version(repo: Path, name: str = "extension.yml") -> str:
    match = re.search(r'^\s*version:\s*"?([0-9][^"\s]*)"?', read(repo / name), re.M)
    return match.group(1) if match else "?"


def bundle_pins(text: str) -> Tuple[str, Dict[str, str], Dict[str, str], str]:
    version = re.search(r'^\s+version:\s*"([^"]+)"', text.split("requires:")[0].split("bundle:")[1], re.M).group(1)
    floor = re.search(r'speckit_version:\s*"([^"]+)"', text).group(1)
    extensions: Dict[str, str] = {}
    presets: Dict[str, str] = {}
    section = None
    for line in text.splitlines():
        if re.match(r"^\s+extensions:\s*$", line):
            section = extensions
        elif re.match(r"^\s+presets:\s*$", line):
            section = presets
        elif re.match(r"^\S", line):
            section = None
        match = re.match(r'^\s+-\s+\{\s*id:\s*"([^"]+)",\s*version:\s*"([^"]+)"', line)
        if match and section is not None:
            section[match.group(1)] = match.group(2)
    return version, extensions, presets, floor


def pinned_template(repo: Path, pin: str) -> Tuple[str, str]:
    """(config-template.yml at tag v<pin> when the checkout has it, else the working tree; where it came from)."""
    try:
        proc = subprocess.run(["git", "-C", str(repo), "show", f"v{pin}:config-template.yml"], capture_output=True,
                              text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        proc = None
    if proc is not None and proc.returncode == 0:
        return proc.stdout, f"at v{pin}"
    return read(repo / "config-template.yml"), f"(working tree; tag v{pin} not in the checkout)"


def floor_of(constraint: str) -> str:
    match = re.search(r">=\s*([0-9][0-9.]*)", constraint or "")
    return match.group(1) if match else "0"


def main() -> int:
    parser = argparse.ArgumentParser(description="consistency check across the four Guardians repositories")
    for ext in SIBLINGS:
        parser.add_argument(f"--{ext}-src", type=Path, default=None, help=f"checkout of spec-kit-{ext} (default: ${ext.upper()}_SRC, else ../spec-kit-{ext})")
    args = parser.parse_args()
    repos: Dict[str, Path] = {"guardians": HERE}
    for ext in SIBLINGS:
        given = getattr(args, f"{ext}_src") or os.environ.get(f"{ext.upper()}_SRC")
        repos[ext] = Path(given).resolve() if given else (HERE.parent / f"spec-kit-{ext}").resolve()
        if not (repos[ext] / "extension.yml").is_file():
            print(f"check-family: {NAMES[ext]} checkout not found at {repos[ext]} (pass --{ext}-src or set {ext.upper()}_SRC)", file=sys.stderr)
            return 2
    load = yaml_loader(repos["auditguard"])
    report = Report()
    bundle_version, ext_pins, preset_pins, bundle_floor = bundle_pins(read(HERE / "bundle" / "bundle.yml"))
    versions = {ext: manifest_version(repos[ext]) for ext in SIBLINGS}
    versions["guardians"] = manifest_version(HERE)
    print(f"Guardians {bundle_version} | family check | " + ", ".join(f"{NAMES[e]} {versions[e]}" for e in SIBLINGS))
    print("")

    # pins
    problems = [f"bundle pins {ext} {pin} but spec-kit-{ext} is at {versions.get(ext)}"
                for ext, pin in ext_pins.items() if versions.get(ext) != pin]
    preset_version = manifest_version(repos["archiguard"], "preset/preset.yml")
    for preset, pin in preset_pins.items():
        if preset == "archiguard-templates" and pin != preset_version:
            problems.append(f"bundle pins {preset} {pin} but archiGuard's preset.yml is at {preset_version}")
    report.result("pins", problems, "every pin equals the sibling's own version: " + ", ".join(f"{e} {v}" for e, v in ext_pins.items()))

    # catalogs
    problems = []
    mine = json.loads(read(HERE / "catalog" / "extensions.json"))["extensions"]
    for ext in SIBLINGS:
        theirs = json.loads(read(repos[ext] / "catalog" / "extensions.json"))["extensions"].get(ext, {})
        for key in CATALOG_KEYS:
            if mine.get(ext, {}).get(key) != theirs.get(key):
                problems.append(f"catalog/extensions.json {ext}.{key} = {mine.get(ext, {}).get(key)!r}, spec-kit-{ext} says {theirs.get(key)!r}")
    my_presets = json.loads(read(HERE / "catalog" / "presets.json"))["presets"]
    their_presets = json.loads(read(repos["archiguard"] / "catalog" / "presets.json"))["presets"]
    for preset in my_presets:
        for key in CATALOG_KEYS:
            if my_presets[preset].get(key) != their_presets.get(preset, {}).get(key):
                problems.append(f"catalog/presets.json {preset}.{key} = {my_presets[preset].get(key)!r}, archiGuard says {their_presets.get(preset, {}).get(key)!r}")
    report.result("catalogs", problems, "every catalog entry equals the sibling's own entry")

    # ci-refs
    problems = []
    for ext, var in (("scopeguard", "SCOPEGUARD_TAG"),):
        text = read(repos["archiguard"] / ".github" / "workflows" / "ci.yml")
        match = re.search(rf"^\s*{var}:\s*v?([0-9][^\s]*)", text, re.M)
        if not match or match.group(1) != ext_pins[ext]:
            problems.append(f"spec-kit-archiguard ci.yml {var} is {match.group(1) if match else 'missing'}, the bundle pins {ext_pins[ext]}")
    text = read(repos["auditguard"] / ".github" / "workflows" / "ci.yml")
    for ext, var in (("scopeguard", "SCOPEGUARD_TAG"), ("archiguard", "ARCHIGUARD_TAG")):
        match = re.search(rf"^\s*{var}:\s*v?([0-9][^\s]*)", text, re.M)
        if not match or match.group(1) != ext_pins[ext]:
            problems.append(f"spec-kit-auditguard ci.yml {var} is {match.group(1) if match else 'missing'}, the bundle pins {ext_pins[ext]}")
    text = read(HERE / ".github" / "workflows" / "ci.yml")
    for ext in SIBLINGS:
        match = re.search(rf"^\s*{ext.upper()}_REF:\s*v?([0-9][^\s]*)", text, re.M)
        if not match or match.group(1) != ext_pins[ext]:
            problems.append(f"ci.yml {ext.upper()}_REF is {match.group(1) if match else 'missing'}, the bundle pins {ext_pins[ext]}")
    report.result("ci-refs", problems, "the siblings' CI pins and the Guardians refs equal the bundle pins")

    # ranges
    problems = []
    ag_cfg = load(read(repos["archiguard"] / "config-template.yml")) or {}
    scope_range = str(((ag_cfg.get("gates") or {}).get("scope") or {}).get("version") or "")
    if not version_satisfies(versions["scopeguard"], scope_range):
        problems.append(f"archiGuard gates.scope.version {scope_range} does not accept scopeGuard {versions['scopeguard']}")
    if scope_range != ARCHIGUARD_SCOPE_RANGE:
        problems.append(f"guardians_core/siblings.py ARCHIGUARD_SCOPE_RANGE is {ARCHIGUARD_SCOPE_RANGE!r}, archiGuard's template says {scope_range!r}")
    au_cfg = load(read(repos["auditguard"] / "config-template.yml")) or {}
    for ext in ("scopeguard", "archiguard"):
        wanted = str(((au_cfg.get("collectors") or {}).get(ext) or {}).get("version") or "")
        if not version_satisfies(versions[ext], wanted):
            problems.append(f"auditGuard collectors.{ext}.version {wanted} does not accept {NAMES[ext]} {versions[ext]}")
        if wanted != AUDITGUARD_COLLECTOR_RANGES[ext]:
            problems.append(f"guardians_core/siblings.py AUDITGUARD_COLLECTOR_RANGES[{ext}] is {AUDITGUARD_COLLECTOR_RANGES[ext]!r}, auditGuard's template says {wanted!r}")
    report.result("ranges", problems, f"archiGuard {scope_range} and auditGuard {AUDITGUARD_COLLECTOR_RANGES} accept the pinned versions")

    # fixtures: the template as released at the pin (the bundle installs that one), else the working tree
    problems, sources = [], []
    for ext in SIBLINGS:
        template, source = pinned_template(repos[ext], ext_pins[ext])
        sources.append(f"{ext} {source}")
        if read(HERE / "tests" / "fixtures" / f"{ext}-config.yml") != template:
            problems.append(f"tests/fixtures/{ext}-config.yml differs from spec-kit-{ext}/config-template.yml {source} (copy it when the pin moves)")
    report.result("fixtures", problems, "the fixtures are the siblings' config templates at the pins (" + ", ".join(sources) + ")")

    # readonly
    problems = []
    ag_ro = [str(p) for p in (((ag_cfg.get("edit_guard") or {}).get("always_readonly")) or [])]
    if ag_ro != ARCHIGUARD_READONLY:
        problems.append(f"guardians_core/siblings.py ARCHIGUARD_READONLY {ARCHIGUARD_READONLY} != archiGuard's template {ag_ro}")
    au_ro = [str(p) for p in (((au_cfg.get("guard") or {}).get("readonly")) or [])]
    if au_ro != AUDITGUARD_READONLY:
        problems.append(f"guardians_core/siblings.py AUDITGUARD_READONLY {AUDITGUARD_READONLY} != auditGuard's template {au_ro}")
    report.result("readonly", problems, "the read-only path defaults equal the siblings' templates")

    # launchers
    problems = []
    for ext, repo in repos.items():
        for launcher in (repo / "scripts" / "bash" / f"{ext}.sh", repo / "scripts" / "powershell" / f"{ext}.ps1"):
            if not launcher.is_file():
                problems.append(f"{launcher.relative_to(repo.parent)} is missing")
            elif f"{ext}-python-ok" not in read(launcher):
                problems.append(f"{launcher.relative_to(repo.parent)} lacks the Windows Store stub guard ({ext}-python-ok marker)")
    report.result("launchers", problems, "all eight launchers carry the family's interpreter search")

    # speckit
    problems = []
    for ext in SIBLINGS:
        match = re.search(r'speckit_version:\s*"([^"]+)"', read(repos[ext] / "extension.yml"))
        theirs = floor_of(match.group(1) if match else "")
        if not version_satisfies(floor_of(bundle_floor), f">={theirs}"):
            problems.append(f"bundle requires speckit {bundle_floor} but {NAMES[ext]} requires {match.group(1) if match else '?'}")
    report.result("speckit", problems, f"the bundle floor {bundle_floor} covers every sibling's requirement")

    # readmes
    problems = []
    for ext in SIBLINGS:
        for doc in ("README.md", "preset/README.md"):
            path = repos[ext] / doc
            if not path.is_file():
                continue
            stale = sorted({m for m in re.findall(rf"releases/download/(v[0-9.]+)/{ext}[a-z-]*\.(?:zip|yml)", read(path)) if m != f"v{versions[ext]}"})
            if stale:
                problems.append(f"spec-kit-{ext}/{doc} links {', '.join(stale)} assets; the current version is v{versions[ext]}")
    for doc in ("README.md", "bundle/README.md"):
        text = read(HERE / doc)
        for ext in SIBLINGS:
            stale = sorted({m for m in re.findall(rf"releases/download/(v[0-9.]+)/{ext}[a-z-]*\.zip", text) if m != f"v{ext_pins[ext]}"})
            if stale:
                problems.append(f"{doc} links {NAMES[ext]} {', '.join(stale)} assets; the bundle pins v{ext_pins[ext]}")
    report.result("readmes", problems, "every README names its own current release")

    print("")
    print(f"RESULT: {'FAIL' if report.failed else 'OK'} | {report.failed} failure(s)")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
