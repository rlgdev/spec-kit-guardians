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
    assert len(data["changes"]) == 6 and data["verify"]["status"] == "warn"


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


# ----- Spec Kit's catalogs ----------------------------------------------------------------------------------

def test_catalogs_of_spec_kit_are_added_back(fresh: FakeProject):
    before = fresh.path(".specify/extension-catalogs.yml").read_text(encoding="utf-8")
    code, out = run(fresh)
    assert code == 0, out
    assert (".specify/extension-catalogs.yml: catalogs += default (priority 1), community (priority 20) - Spec Kit's own "
            "extension catalogs, which this file replaced") in out
    assert ".specify/preset-catalogs.yml: catalogs += default (priority 1), community (priority 20)" in out
    after = fresh.path(".specify/extension-catalogs.yml").read_text(encoding="utf-8")
    assert after.startswith(before)                                   # an append: the Guardians entry is untouched
    entries = yaml.safe_load(after)["catalogs"]
    # exactly what `specify extension catalog add <url> --name default --priority 1 --install-allowed` writes, so a
    # later run of that command is a no-op
    assert entries[1:] == [
        {"name": "default", "url": "https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.json",
         "priority": 1, "install_allowed": True, "description": ""},
        {"name": "community", "url": "https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json",
         "priority": 20, "install_allowed": False, "description": ""}]
    presets = yaml.safe_load(fresh.path(".specify/preset-catalogs.yml").read_text(encoding="utf-8"))["catalogs"]
    assert [e["url"].rsplit("/", 2)[-2:] for e in presets[1:]] == [["presets", "catalog.json"], ["presets", "catalog.community.json"]]
    assert "[OK]   catalogs_keep_defaults" in out


def test_catalogs_that_are_not_only_the_familys_are_left_alone(fresh: FakeProject, _speckit_environment: Path):
    corporate = "catalogs:\n- name: corp\n  url: https://catalog.example.com/x.json\n  priority: 1\n  install_allowed: true\n"
    fresh.write(".specify/extension-catalogs.yml", corporate)
    user = _speckit_environment / ".specify" / "preset-catalogs.yml"   # the user's catalogs: not copied into the project
    user.parent.mkdir(parents=True)
    user.write_text("catalogs:\n- name: mine\n  url: https://catalog.example.com/p.json\n", encoding="utf-8")
    preset_before = fresh.path(".specify/preset-catalogs.yml").read_text(encoding="utf-8")
    code, out = run(fresh)
    assert fresh.path(".specify/extension-catalogs.yml").read_text(encoding="utf-8") == corporate
    assert fresh.path(".specify/preset-catalogs.yml").read_text(encoding="utf-8") == preset_before
    assert "catalogs +=" not in out and "[WARN] catalogs_keep_defaults" in out and code == 0


def test_catalog_repair_keeps_crlf_and_refuses_an_unexpected_shape(fresh: FakeProject):
    path = fresh.path(".specify/extension-catalogs.yml")
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    flow = "catalogs: [{name: guardians, url: 'https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/presets.json'}]\n"
    fresh.write(".specify/preset-catalogs.yml", flow)
    code, out = run(fresh)
    data = path.read_bytes()
    assert b"name: default\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
    assert fresh.path(".specify/preset-catalogs.yml").read_text(encoding="utf-8") == flow
    assert ("NOTE: could not edit .specify/preset-catalogs.yml (unexpected shape); add Spec Kit's catalogs by hand: "
            "specify preset catalog add https://raw.githubusercontent.com/github/spec-kit/main/presets/catalog.json "
            "--name default --priority 1 --install-allowed") in out


# ----- the agent events ------------------------------------------------------------------------------------

WIRE = "specify extension disable guardians && specify extension enable guardians"


def test_agent_events_are_wired_through_spec_kit(fresh: FakeProject):
    code, out = run(fresh)
    assert code == 0, out
    assert fresh.specify_calls() == ["extension disable guardians", "extension enable guardians"]
    assert f"agent events of archiGuard, auditGuard for claude: wired by Spec Kit ({WIRE})" in out
    settings = fresh.path(".claude/settings.json").read_text(encoding="utf-8")
    assert "speckit.archiguard.editguard" in settings and "speckit.auditguard.guard" in settings
    assert "[OK]   agent_events_wired" in out
    run(fresh)
    assert len(fresh.specify_calls()) == 2                            # wired: the second run calls nothing


def test_agent_events_dry_run_calls_nothing(fresh: FakeProject):
    code, out = run(fresh, "--dry-run")
    assert fresh.specify_calls() == []
    assert f"agent events of archiGuard, auditGuard for claude: {WIRE} (Spec Kit wires them)" in out


def test_agent_events_without_specify_or_when_guardians_is_disabled(fresh: FakeProject, monkeypatch):
    from guardians_core import speckit
    monkeypatch.setattr(speckit, "specify_command", lambda: None)
    code, out = run(fresh)
    assert code == 0 and (f"NOTE: the agent events of archiGuard, auditGuard for claude are not wired (specify is not on "
                          f"PATH): run {WIRE}") in out
    assert "[WARN] agent_events_wired" in out


def test_agent_events_are_not_toggled_for_a_disabled_guardians_or_the_generic_integration(fresh: FakeProject):
    fresh.write(".specify/extensions/.registry", json.dumps({"extensions": {"guardians": {"enabled": False}}}))
    code, out = run(fresh)
    assert fresh.specify_calls() == [] and "are not wired (Guardians is disabled in Spec Kit): run" in out
    fresh.path(".specify/extensions/.registry").unlink()
    fresh.write(".specify/init-options.json", json.dumps({"ai": "generic"}))
    code, out = run(fresh)
    assert fresh.specify_calls() == [] and "are not wired (the generic integration): run" in out


def test_agent_events_when_spec_kit_fails(fresh: FakeProject):
    fresh.write(".specify/SPECIFY_FAIL", "disable")
    code, out = run(fresh)
    assert code == 0 and fresh.specify_calls() == ["extension disable guardians"]
    assert "NOTE: specify extension disable guardians exited 1 (Error: disable failed on purpose); the agent events" in out
    fresh.write(".specify/SPECIFY_FAIL", "enable")
    code, out = run(fresh)
    assert code == 2 and ("ERROR: specify extension enable guardians exited 1 (Error: enable failed on purpose): Guardians "
                          "is left disabled in Spec Kit - run specify extension enable guardians") in out
    fresh.path(".specify/SPECIFY_FAIL").unlink()
    fresh.write(".specify/SPECIFY_NOWIRE", "")                       # a Spec Kit whose enable wires nothing
    fresh.write(".specify/extensions/.registry", json.dumps({"extensions": {}}))
    fresh.write(".claude/settings.json", "{}\n")
    code, out = run(fresh)
    assert "NOTE: Spec Kit did not wire the agent events of archiGuard, auditGuard for claude" in out


# ----- line endings ----------------------------------------------------------------------------------------

def test_crlf_files_keep_their_line_endings(fresh: FakeProject):
    """Spec Kit writes .specify/extensions.yml with CRLF on Windows; the line edits keep it, so git shows their lines."""
    lf = make_project(fresh.root.parent / "lf", aligned=False)
    for project in (fresh, lf):
        if project is fresh:
            for rel in (".specify/extensions.yml", ".specify/extensions/scopeguard/scopeguard-config.yml",
                        ".specify/extensions/archiguard/archiguard-config.yml"):
                path = project.path(rel)
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        assert run(project)[0] == 0
    for rel in (".specify/extensions.yml", ".specify/extensions/scopeguard/scopeguard-config.yml",
                ".specify/extensions/archiguard/archiguard-config.yml"):
        assert fresh.path(rel).read_bytes() == lf.path(rel).read_bytes().replace(b"\n", b"\r\n"), rel
