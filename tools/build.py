#!/usr/bin/env python3
"""Build the release archives of Guardians and check that every pin and version agrees.

    python tools/build.py                 # dist/guardians.zip, dist/guardians-bundle.zip, dist/SHA256SUMS
    python tools/build.py --check         # fail when a version or pin disagrees, or a referenced file is missing (CI)
    python tools/build.py --check-tag v0.1.0

What must agree:
  - the Guardians version: extension.yml, guardians_core/__init__.py, bundle/bundle.yml (bundle version and the
    `guardians` pin), catalog/extensions.json (guardians), catalog/bundles.json
  - every sibling pin in bundle/bundle.yml and its catalog entry (catalog/extensions.json, catalog/presets.json)
  - the sibling action versions in action.yml and the bundle pins
Both archives are reproducible: fixed timestamps, sorted entries, normalised modes. guardians.zip has
extension.yml at its root (what `specify extension add --from` expects); guardians-bundle.zip has bundle.yml and
README.md at its root (what `specify bundle build` produces).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
FIXED_DATE = (2026, 1, 1, 0, 0, 0)
EXTENSION_FILES = ["extension.yml", "config-template.yml", "README.md", "LICENSE", "CHANGELOG.md"]
EXTENSION_DIRS = ["commands", "scripts"]
BUNDLE_DIR = ROOT / "bundle"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def first(pattern: str, text: str, where: str) -> str:
    match = re.search(pattern, text, re.M)
    if not match:
        raise SystemExit(f"{where}: pattern not found: {pattern}")
    return match.group(1)


def bundle_pins() -> Tuple[str, Dict[str, str], Dict[str, str]]:
    """(bundle version, extension id -> pin, preset id -> pin) from bundle/bundle.yml."""
    text = read(BUNDLE_DIR / "bundle.yml")
    version = first(r'^\s+version:\s*"([^"]+)"', text.split("requires:")[0].split("bundle:")[1], "bundle.yml bundle.version")
    extensions, presets = {}, {}
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
    return version, extensions, presets


def versions() -> Tuple[str, List[str]]:
    """The Guardians version and a list of disagreements."""
    problems: List[str] = []
    found = {
        "extension.yml": first(r'^\s*version:\s*"?([0-9][^"\s]*)"?', read(ROOT / "extension.yml"), "extension.yml"),
        "guardians_core/__init__.py": first(r'^__version__\s*=\s*"([^"]+)"', read(ROOT / "scripts/python/guardians_core/__init__.py"), "__init__.py"),
    }
    bundle_version, ext_pins, preset_pins = bundle_pins()
    found["bundle/bundle.yml (bundle)"] = bundle_version
    found["bundle/bundle.yml (guardians pin)"] = ext_pins.get("guardians", "?")
    extensions = json.loads(read(ROOT / "catalog/extensions.json"))["extensions"]
    presets = json.loads(read(ROOT / "catalog/presets.json"))["presets"]
    bundles = json.loads(read(ROOT / "catalog/bundles.json"))["bundles"]
    found["catalog/extensions.json (guardians)"] = extensions.get("guardians", {}).get("version", "?")
    found["catalog/bundles.json"] = bundles.get("guardians", {}).get("version", "?")
    if len(set(found.values())) != 1:
        problems.append(f"Guardians version disagrees: {found}")
    for ext_id, pin in ext_pins.items():
        if ext_id not in extensions:
            problems.append(f"bundle pins extension {ext_id} {pin} but catalog/extensions.json has no entry for it")
        elif extensions[ext_id].get("version") != pin:
            problems.append(f"extension {ext_id}: bundle pins {pin}, catalog/extensions.json says {extensions[ext_id].get('version')}")
        elif not str(extensions[ext_id].get("download_url", "")).startswith("https://"):
            problems.append(f"extension {ext_id}: catalog download_url must be https")
    for preset_id, pin in preset_pins.items():
        if preset_id not in presets:
            problems.append(f"bundle pins preset {preset_id} {pin} but catalog/presets.json has no entry for it")
        elif presets[preset_id].get("version") != pin:
            problems.append(f"preset {preset_id}: bundle pins {pin}, catalog/presets.json says {presets[preset_id].get('version')}")
    bundle_entry = bundles.get("guardians", {})
    counts = bundle_entry.get("provides", {})
    if counts.get("extensions") != len(ext_pins) or counts.get("presets") != len(preset_pins):
        problems.append(f"catalog/bundles.json provides counts {counts} do not match the bundle ({len(ext_pins)} extensions, {len(preset_pins)} presets)")
    action = read(ROOT / "action.yml")
    for ext_id in ("scopeguard", "archiguard", "auditguard"):
        used = re.findall(rf"rlgdev/spec-kit-{ext_id}@v([0-9][^\s'\"]*)", action)
        if not used:
            problems.append(f"action.yml does not use rlgdev/spec-kit-{ext_id}")
        elif any(u != ext_pins.get(ext_id) for u in used):
            problems.append(f"action.yml uses rlgdev/spec-kit-{ext_id}@v{used[0]} but the bundle pins {ext_pins.get(ext_id)}")
    for ext_id, entry in extensions.items():
        if entry.get("id") != ext_id:
            problems.append(f"catalog/extensions.json: key {ext_id} has id {entry.get('id')}")
    if not (BUNDLE_DIR / "README.md").is_file():
        problems.append("bundle/README.md is missing (specify bundle build requires it)")
    manifest = read(ROOT / "extension.yml")
    for command in re.findall(r"file:\s*(commands/[^\s}]+)", manifest):
        if not (ROOT / command).is_file():
            problems.append(f"extension.yml names a command file that does not exist: {command}")
    if first(r"^\s+id:\s*(\S+)", manifest, "extension.yml id") != "guardians":
        problems.append("extension.yml id is not guardians (rename everywhere, or change this check)")
    return found["extension.yml"], problems


def add_file(zf: zipfile.ZipFile, source: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
    executable = source.suffix in (".sh", ".py") and "scripts" in source.parts
    info.external_attr = ((0o100755 if executable else 0o100644) & 0xFFFF) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, source.read_bytes())


def collect_extension() -> List[Tuple[Path, str]]:
    entries = [(ROOT / name, name) for name in EXTENSION_FILES]
    for directory in EXTENSION_DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                entries.append((path, path.relative_to(ROOT).as_posix()))
    return entries


def collect_bundle() -> List[Tuple[Path, str]]:
    return [(path, path.relative_to(BUNDLE_DIR).as_posix()) for path in sorted(BUNDLE_DIR.rglob("*")) if path.is_file()]


def build(target: Path, entries: List[Tuple[Path, str]]) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w") as zf:
        for source, arcname in sorted(entries, key=lambda e: e[1]):
            add_file(zf, source, arcname)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="only check: versions and pins agree, files exist")
    parser.add_argument("--check-tag", help="fail unless the version equals this tag (with or without leading v)")
    args = parser.parse_args()
    version, problems = versions()
    if args.check_tag and args.check_tag.lstrip("v") != version:
        problems.append(f"tag {args.check_tag} does not match version {version}")
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    if args.check:
        print(f"ok: version {version}, pins and catalogs agree")
        return 0
    sums = []
    for name, entries in (("guardians.zip", collect_extension()), ("guardians-bundle.zip", collect_bundle())):
        digest = build(DIST / name, entries)
        sums.append(f"{digest}  {name}")
        print(f"built dist/{name} ({len(entries)} files) sha256={digest}")
    (DIST / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(f"version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
