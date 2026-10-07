"""configure: cross-wiring, the siblings in order, hook priorities, dry run, idempotence, a failing sibling."""

import json
from pathlib import Path

import yaml

from conftest import VERSIONS, FakeProject, guardians_cli, make_project


def run(project: FakeProject, *args: str):
    return guardians_cli("configure", "--root", str(project.root), *args)


def calls(project: FakeProject):
    """[(extension, 'run' | 'dry'), ...] in the order the stubs were called."""
    words = project.runs()
    return list(zip(words[0::2], words[1::2]))


def real_runs(project: FakeProject):
    return [ext for ext, kind in calls(project) if kind == "run"]


def test_fresh_project_becomes_aligned(fresh: FakeProject):
    before = {ext: fresh.config(ext) for ext in ("scopeguard", "archiguard", "auditguard")}
    code, out = run(fresh)
    assert code == 0, out
    # US2: the three files
    assert yaml.safe_load(fresh.config("scopeguard"))["integration"] == "embedded"
    readonly = yaml.safe_load(fresh.config("archiguard"))["edit_guard"]["always_readonly"]
    assert readonly[-2:] == ["audit/**", ".specify/extensions/auditguard/**"]
    assert fresh.config("auditguard") == before["auditguard"]           # never written
    registry = yaml.safe_load(fresh.registry())
    for event, entries in registry["hooks"].items():
        for entry in entries:
            if entry["extension"] == "auditguard":
                assert entry["priority"] == (1 if event.startswith("before_") else 90)
            else:
                assert entry["priority"] == 10 and entry["enabled"] is True   # enabled flags belong to the siblings
    # the siblings ran in order, after the cross-wiring, for real
    assert real_runs(fresh) == ["scopeguard", "archiguard", "auditguard"]
    # the report
    assert "Changed:" in out
    assert "scopeguard-config.yml: integration: inline -> embedded" in out
    assert "archiguard-config.yml: edit_guard.always_readonly += audit/**, .specify/extensions/auditguard/**" in out
    assert "extensions.yml: 20 hook priorities set: auditguard after_* 10 -> 90 (10), auditguard before_* 10 -> 1 (10)" in out
    assert f"scopeGuard : scopeGuard {VERSIONS['scopeguard']} | configure | integration embedded" in out
    assert "[OK]   scopeguard_embedded" in out and "[OK]   edit_guard_covers_audit" in out and "[OK]   hook_order" in out
    # exit 0 even though the stub siblings do not switch their hooks off (that is their job; it is a warning here)
    assert "[WARN] hooks_match_integration" in out and "RESULT: WARN" in out
    # only the comment lines of the siblings' templates are unchanged - the files still parse and keep their size
    assert len(fresh.config("scopeguard").splitlines()) == len(before["scopeguard"].splitlines())
    assert len(fresh.config("archiguard").splitlines()) == len(before["archiguard"].splitlines())


def test_archiguard_status_is_consulted_before_the_scopeguard_edit(fresh: FakeProject):
    """The scopeGuard edit depends on archiGuard's dry-run JSON (scope_in_pipeline), queried before the configures."""
    run(fresh)
    assert calls(fresh)[0] == ("archiguard", "dry")
    assert calls(fresh).index(("scopeguard", "run")) > 0


def test_dry_run_changes_nothing(fresh: FakeProject):
    snapshot = {p: p.read_bytes() for p in fresh.root.rglob("*") if p.is_file()}
    code, out = run(fresh, "--dry-run")
    assert code == 1, out                      # the FAILs remain, nothing was changed
    assert "Would change:" in out and "(dry run)" in out
    after = {p: p.read_bytes() for p in fresh.root.rglob("*") if p.is_file() and p.name != "stub-runs.log"}
    assert {p: b for p, b in snapshot.items() if p.name != "stub-runs.log"} == after
    assert all(r in ("scopeguard", "archiguard", "auditguard", "dry") for r in fresh.runs())


def test_second_run_changes_nothing(fresh: FakeProject):
    run(fresh)
    snapshot = {p: p.read_bytes() for p in fresh.root.rglob("*") if p.is_file() and p.name != "stub-runs.log"}
    code, out = run(fresh)
    assert code == 0 and "No change needed." in out and "Changed:" not in out
    after = {p: p.read_bytes() for p in fresh.root.rglob("*") if p.is_file() and p.name != "stub-runs.log"}
    assert snapshot == after


def test_aligned_project_needs_nothing(aligned: FakeProject):
    code, out = run(aligned)
    assert code == 0 and "No change needed." in out and "RESULT: OK" in out


def test_failing_sibling_stops_the_run(fresh: FakeProject):
    fresh.write(".specify/extensions/archiguard/FAIL", "3")
    code, out = run(fresh)
    assert code == 2
    assert "archiGuard : configure exited 3" in out and "configure failed on purpose" in out
    assert "ERROR: archiGuard configure failed (exit 3); nothing after it ran" in out
    assert real_runs(fresh) == ["scopeguard", "archiguard"]   # archiGuard was called and failed; auditGuard never ran
    # the cross-wiring edits made before the failure stay (they are the siblings' documented requirements)...
    assert yaml.safe_load(fresh.config("archiguard"))["edit_guard"]["always_readonly"][-1] == ".specify/extensions/auditguard/**"
    # ...but the scopeGuard edit depends on archiGuard's status, which this stub refuses
    assert yaml.safe_load(fresh.config("scopeguard"))["integration"] == "inline"
    assert "NOTE: archiGuard's status is unavailable" in out


def test_no_siblings_skips_their_configures(fresh: FakeProject):
    code, out = run(fresh, "--no-siblings")
    assert code == 0 and "Siblings:" not in out
    assert real_runs(fresh) == []                      # only the dry-run status queries


def test_json_output(fresh: FakeProject):
    code, out = run(fresh, "--json")
    data = json.loads(out)
    assert code == 0 and data["exit_code"] == 0
    assert [s["id"] for s in data["siblings"]] == ["scopeguard", "archiguard", "auditguard"]
    assert len(data["changes"]) == 3 and data["verify"]["status"] == "warn"


def test_custom_order_and_priorities(fresh: FakeProject):
    fresh.write(".specify/extensions/guardians/guardians-config.yml",
                "order: [auditguard, archiguard, scopeguard]\nhook_priority:\n  auditguard: {before: 2, after: 80}\n  default: 20\n")
    code, out = run(fresh)
    assert code == 0, out
    assert real_runs(fresh) == ["auditguard", "archiguard", "scopeguard"]
    registry = yaml.safe_load(fresh.registry())
    assert registry["hooks"]["before_plan"][2]["priority"] == 2 and registry["hooks"]["after_plan"][2]["priority"] == 80
    assert registry["hooks"]["after_plan"][0]["priority"] == 10     # existing priorities of the gates are kept


def test_missing_registry_is_reported_not_fatal(tmp_path: Path):
    project = make_project(tmp_path / "noreg", aligned=False)
    (project.root / ".specify" / "extensions.yml").unlink()
    code, out = run(project)
    assert code == 0 and "extensions.yml not found - no hooks registered yet" in out


def test_without_archiguard_scopeguard_keeps_its_integration(tmp_path: Path):
    project = make_project(tmp_path / "noag", aligned=False, siblings=("scopeguard", "auditguard"), preset=False)
    code, out = run(project)
    assert code == 1                                            # installed: archiguard missing
    assert yaml.safe_load(project.config("scopeguard"))["integration"] == "inline"
    assert "archiGuard : not installed - skipped" in out
    assert "[FAIL] installed" in out


def test_missing_sibling_configs_say_how_to_create_them(fresh: FakeProject):
    # a bundle install on Spec Kit 1.0.1 / 1.0.2 does not copy the config templates: configure names the copy to make
    # and writes nothing in their place (creating a sibling's config is not one of the three things Guardians writes)
    for ext in ("scopeguard", "archiguard"):
        fresh.config_path(ext).unlink()
    code, out = run(fresh)
    assert code == 1, out
    for ext in ("scopeguard", "archiguard"):
        d = f".specify/extensions/{ext}"
        assert f"NOTE: {d}/{ext}-config.yml not found: copy {d}/config-template.yml to {d}/{ext}-config.yml, then run guardians configure again" in out
        assert not fresh.config_path(ext).exists()
    assert "creates it" not in out
