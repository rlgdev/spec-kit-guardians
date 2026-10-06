"""guardians-config.yml validation, and the YAML reader fallback to an installed sibling's reader."""

import os
import shutil
from pathlib import Path

import pytest

from conftest import FakeProject, make_project
from guardians_core import yamlio
from guardians_core.common import GuardiansError, version_satisfies
from guardians_core.config import DEFAULTS, load_config


def write_config(project: FakeProject, text: str) -> None:
    project.write(".specify/extensions/guardians/guardians-config.yml", text)


def test_defaults_when_absent(aligned: FakeProject):
    cfg = load_config(aligned.root)
    assert cfg.path is None and cfg.order == ["scopeguard", "archiguard", "auditguard"]
    assert cfg.priority("auditguard", "before_plan", 10) == 1 and cfg.priority("auditguard", "after_plan", 10) == 90
    assert cfg.priority("scopeguard", "after_plan", None) == 10 and cfg.priority("scopeguard", "after_plan", 7) is None
    assert cfg.priority("git", "after_plan", None) is None
    assert cfg.severity("git_base_agrees") == "fail" and cfg.severity("codeowners") == "warn"


def test_template_equals_defaults(aligned: FakeProject):
    """config-template.yml documents the defaults - it must load to exactly them."""
    template = Path(__file__).resolve().parents[1] / "config-template.yml"
    write_config(aligned, template.read_text(encoding="utf-8"))
    assert load_config(aligned.root).data == DEFAULTS


@pytest.mark.parametrize("text, fragment", [
    ("nonsense: 1\n", "unknown key(s) nonsense"),
    ("version: 2\n", "version must be 1"),
    ("order: [scopeguard, scopeguard]\n", "order must list"),
    ("order: [jira]\n", "order must list"),
    ("hook_priority: {auditguard: {before: 0}}\n", "must be an integer >= 1"),
    ("hook_priority: {auditguard: {middle: 5}}\n", "allows the keys before and after"),
    ("hook_priority: {default: true}\n", "must be an integer >= 1"),
    ("checks: {bogus: fail}\n", "unknown check(s) bogus"),
    ("checks: {codeowners: maybe}\n", "must be one of fail, warn, off"),
    ("checks: [a, b]\n", "checks must be a mapping"),
])
def test_invalid_configs(aligned: FakeProject, text: str, fragment: str):
    write_config(aligned, text)
    with pytest.raises(GuardiansError) as exc:
        load_config(aligned.root)
    assert fragment in str(exc.value)


def test_explicit_config_path(aligned: FakeProject, tmp_path: Path):
    path = tmp_path / "mine.yml"
    path.write_text("order: [auditguard]\n", encoding="utf-8")
    assert load_config(aligned.root, path).order == ["auditguard"]
    with pytest.raises(GuardiansError):
        load_config(aligned.root, tmp_path / "missing.yml")


def test_version_satisfies():
    assert version_satisfies("0.4.0", ">=0.4,<0.6") and not version_satisfies("0.6.0", ">=0.4,<0.6")
    assert version_satisfies("0.4.0", ">=0.3.0,<0.5") and not version_satisfies("0.5.0", ">=0.3.0,<0.5")
    assert version_satisfies("1.2.3", "~=1.2") and not version_satisfies("1.3.0", "~=1.2.0")
    assert version_satisfies("0.1.0", "") and version_satisfies("0.1.0", "!=0.2.0")


def test_reader_is_pyyaml_here():
    yamlio.set_search_root(Path("/nonexistent"))
    assert yamlio.loads("a: 1\nb: [x, y]\nd: 2026-10-06\n") == {"a": 1, "b": ["x", "y"], "d": "2026-10-06"}
    assert yamlio.reader_name() == "PyYAML"


def test_fallback_to_a_sibling_reader(tmp_path: Path, monkeypatch):
    """Without PyYAML, the reader of the installed auditGuard (or archiGuard) is used."""
    src = os.environ.get("AUDITGUARD_SRC")
    if not src or not (Path(src) / "scripts" / "python" / "auditguard_core" / "yamlio.py").is_file():
        pytest.skip("set AUDITGUARD_SRC to a spec-kit-auditguard checkout")
    project = make_project(tmp_path / "fallback", aligned=True)
    target = project.root / ".specify" / "extensions" / "auditguard" / "scripts" / "python" / "auditguard_core"
    shutil.copytree(Path(src) / "scripts" / "python" / "auditguard_core", target)
    monkeypatch.setattr(yamlio, "_pyyaml", lambda: None)
    yamlio.set_search_root(project.root)
    try:
        data = yamlio.load_file(project.config_path("archiguard"))
        assert yamlio.reader_name() == "auditguard_core.yamlio"
        assert data["edit_guard"]["always_readonly"][-1] == ".specify/extensions/auditguard/**"
        assert data["git"]["base"] == "main"
        with pytest.raises(GuardiansError):
            yamlio.loads("a: [unclosed", "x")
    finally:
        yamlio.set_search_root(Path("/nonexistent"))


def test_no_reader_at_all(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(yamlio, "_pyyaml", lambda: None)
    yamlio.set_search_root(tmp_path)
    with pytest.raises(GuardiansError) as exc:
        yamlio.loads("a: 1")
    assert "install PyYAML" in str(exc.value)
    yamlio.set_search_root(Path("/nonexistent"))
