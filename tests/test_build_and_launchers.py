"""tools/build.py (pins and versions agree, reproducible archives) and the launchers."""

import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from conftest import REPO, requires_bash

BUILD = REPO / "tools" / "build.py"


def run(*args: str, cwd: Path = REPO):
    return subprocess.run([sys.executable, *args], cwd=str(cwd), capture_output=True, text=True)


def test_check_passes():
    proc = run(str(BUILD), "--check")
    assert proc.returncode == 0, proc.stderr
    assert "pins and catalogs agree" in proc.stdout


def test_check_tag():
    assert run(str(BUILD), "--check", "--check-tag", "v0.1.0").returncode == 0
    proc = run(str(BUILD), "--check", "--check-tag", "v9.9.9")
    assert proc.returncode == 1 and "does not match" in proc.stderr


def test_build_is_reproducible(tmp_path: Path):
    proc = run(str(BUILD))
    assert proc.returncode == 0, proc.stderr
    dist = REPO / "dist"
    ext = zipfile.ZipFile(dist / "guardians.zip")
    names = ext.namelist()
    assert "extension.yml" in names and "commands/speckit.guardians.configure.md" in names
    assert "scripts/python/guardians_core/configure.py" in names and "scripts/bash/guardians.sh" in names
    assert not any(n.startswith(("tests/", "tools/", "bundle/", "catalog/", ".github/")) for n in names)
    bundle = zipfile.ZipFile(dist / "guardians-bundle.zip")
    assert sorted(bundle.namelist()) == ["README.md", "bundle.yml"]
    first = hashlib.sha256((dist / "guardians.zip").read_bytes()).hexdigest()
    sums = (dist / "SHA256SUMS").read_text(encoding="utf-8")
    assert f"{first}  guardians.zip" in sums and "guardians-bundle.zip" in sums
    run(str(BUILD))
    assert hashlib.sha256((dist / "guardians.zip").read_bytes()).hexdigest() == first


def test_catalog_download_urls_are_release_assets():
    import json
    extensions = json.loads((REPO / "catalog" / "extensions.json").read_text(encoding="utf-8"))["extensions"]
    for ext_id, entry in extensions.items():
        assert entry["download_url"] == f"https://github.com/rlgdev/spec-kit-{ext_id}/releases/download/v{entry['version']}/{ext_id}.zip"
    bundles = json.loads((REPO / "catalog" / "bundles.json").read_text(encoding="utf-8"))["bundles"]
    assert bundles["guardians"]["download_url"].endswith("/v0.1.0/guardians-bundle.zip")


def test_python_launcher(tmp_path: Path):
    proc = run(str(REPO / "scripts" / "python" / "guardians.py"), "version", cwd=tmp_path)
    assert proc.returncode == 0 and proc.stdout.strip() == "Guardians 0.1.0"
    proc = run(str(REPO / "scripts" / "python" / "guardians.py"), "verify", cwd=tmp_path)
    assert proc.returncode == 2 and "no Spec Kit project found" in proc.stderr


@pytest.mark.skipif(not requires_bash(), reason="bash launcher is covered by the CI launchers job on Windows")
def test_bash_launcher(tmp_path: Path):
    env = dict(os.environ, GUARDIANS_PYTHON=sys.executable)
    proc = subprocess.run(["bash", str(REPO / "scripts" / "bash" / "guardians.sh"), "version"], cwd=str(tmp_path),
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0 and proc.stdout.strip() == "Guardians 0.1.0"
    env["GUARDIANS_PYTHON"] = "/no/such/python"
    proc = subprocess.run(["bash", str(REPO / "scripts" / "bash" / "guardians.sh"), "version"], cwd=str(tmp_path),
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 2 and "not a working Python" in proc.stderr
