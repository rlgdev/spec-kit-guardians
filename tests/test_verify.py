"""verify: an aligned project passes every check; each check is made to fail by one change (SC-002)."""

from pathlib import Path


from conftest import (GUARDIANS_VERSION, VERSIONS, FakeProject, all_enabled, default_priority, guardians_cli, make_project,
                      registry_text)
from guardians_core.config import CHECKS, load_config
from guardians_core.siblings import Project
from guardians_core.verify import run_verify


def verify(project: FakeProject):
    p = Project(project.root)
    return run_verify(p, load_config(project.root))


def status_of(report, check_id: str) -> str:
    return next(c for c in report.checks if c.id == check_id).status


def test_aligned_project_passes_every_check(aligned: FakeProject):
    report = verify(aligned)
    assert [c.id for c in report.checks] == list(CHECKS)
    assert {c.id: c.status for c in report.checks} == {c: "ok" for c in CHECKS}, report.text()
    assert report.status == "ok" and not report.failed
    tools = report.tools
    assert tools["scopeguard"]["integration"] == "embedded" and tools["scopeguard"]["hooks_on"] == 0
    assert tools["archiguard"]["effective_integration"] == "inline" and tools["archiguard"]["scope_in_pipeline"] is True
    assert tools["auditguard"]["hooks_on"] == 20 and tools["auditguard"]["mode"] == "record"
    assert tools["guardians"]["version"] == VERSIONS["guardians"]
    text = report.text()
    assert f"RESULT: OK | {len(CHECKS)} ok, 0 warnings, 0 failures" in text
    assert f"scopeGuard : {VERSIONS['scopeguard']} | integration embedded | mode enforce | hooks 0/5" in text


def test_fresh_project_has_the_expected_failures(fresh: FakeProject):
    report = verify(fresh)
    statuses = {c.id: c.status for c in report.checks}
    assert statuses["scopeguard_embedded"] == "fail"
    assert statuses["edit_guard_covers_audit"] == "fail"
    assert statuses["hook_order"] == "fail"               # every hook enabled at priority 10
    assert statuses["hooks_match_integration"] == "warn"  # inline / embedded tools with hooks on
    assert statuses["gitattributes"] == "warn"
    assert statuses["installed"] == "ok" and statuses["git_base_agrees"] == "ok"
    assert statuses["catalogs_keep_defaults"] == "warn"   # the Guardians catalogs alone (the old install docs)
    assert statuses["agent_events_wired"] == "warn"       # a bundle install does not wire them
    assert report.status == "fail"
    fixes = {c.id: c.fix for c in report.checks}
    assert "guardians configure" in fixes["scopeguard_embedded"] and "guardians configure" in fixes["edit_guard_covers_audit"]
    assert fixes["catalogs_keep_defaults"].startswith("guardians configure (adds default, community back to")
    assert fixes["agent_events_wired"] == ("guardians configure (runs specify extension disable guardians && "
                                           "specify extension enable guardians)")


# ----- one change per check -------------------------------------------------------------------------------

def test_installed(aligned: FakeProject):
    aligned.remove_extension("auditguard")
    report = verify(aligned)
    check = next(c for c in report.checks if c.id == "installed")
    assert check.status == "fail" and "auditguard" in check.message and check.fix == "specify bundle install guardians"
    assert report.tools["auditguard"] == {"installed": False}


def check_of(project: FakeProject, check_id: str):
    return next(c for c in verify(project).checks if c.id == check_id)


def test_catalogs_keep_defaults(aligned: FakeProject, fresh: FakeProject):
    check = check_of(aligned, "catalogs_keep_defaults")
    assert check.status == "ok" and check.message == ("extensions: .specify/extension-catalogs.yml keeps default, community; "
                                                      "presets: .specify/preset-catalogs.yml keeps default, community")
    check = check_of(fresh, "catalogs_keep_defaults")
    assert check.status == "warn"
    assert check.message.startswith(".specify/extension-catalogs.yml replaces Spec Kit's extension catalogs and lacks "
                                    "default, community: other extensions are missing from search, info and update; "
                                    ".specify/preset-catalogs.yml replaces")
    # no project file: Spec Kit's own catalogs (or the user's) are in force
    for kind in ("extension", "preset"):
        aligned.path(f".specify/{kind}-catalogs.yml").unlink()
    check = check_of(aligned, "catalogs_keep_defaults")
    assert check.status == "ok" and "extensions: Spec Kit's own catalogs (no .specify/extension-catalogs.yml)" in check.message


def test_catalogs_a_corporate_stack_is_named_not_repaired(fresh: FakeProject):
    fresh.write(".specify/extension-catalogs.yml", "catalogs:\n- name: corp\n  url: https://catalog.example.com/x.json\n"
                "  priority: 1\n  install_allowed: true\n")
    check = check_of(fresh, "catalogs_keep_defaults")
    assert check.status == "warn" and "lacks default, community" in check.message
    assert check.fix.startswith("specify extension catalog add https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.json "
                                "--name default --priority 1 --install-allowed / specify extension catalog add ")
    assert "--name community --priority 20 --no-install-allowed - or switch this check off" in check.fix


def test_catalogs_the_user_level_file_is_what_is_replaced(fresh: FakeProject, _speckit_environment: Path):
    user = _speckit_environment / ".specify" / "extension-catalogs.yml"
    user.parent.mkdir(parents=True)
    user.write_text("catalogs:\n- name: corp\n  url: https://catalog.example.com/x.json\n", encoding="utf-8")
    check = check_of(fresh, "catalogs_keep_defaults")
    assert "extension-catalogs.yml replaces Spec Kit's extension catalogs and lacks corp:" in check.message
    assert "copy the entries of ~/.specify/extension-catalogs.yml into .specify/extension-catalogs.yml" in check.fix
    fresh.write(".specify/extension-catalogs.yml", user.read_text(encoding="utf-8") + fresh.path(
        ".specify/extension-catalogs.yml").read_text(encoding="utf-8").replace("catalogs:\n", ""))
    fresh.path(".specify/preset-catalogs.yml").unlink()
    check = check_of(fresh, "catalogs_keep_defaults")
    assert check.status == "ok" and check.message.startswith("extensions: .specify/extension-catalogs.yml keeps corp;")


def test_catalogs_empty_files_and_the_environment(aligned: FakeProject, monkeypatch):
    aligned.write(".specify/extension-catalogs.yml", "catalogs: []\n")
    aligned.write(".specify/preset-catalogs.yml", "catalogs: []\n")    # presets: Spec Kit falls back to its own
    check = check_of(aligned, "catalogs_keep_defaults")
    assert check.status == "warn" and check.message == (".specify/extension-catalogs.yml lists no catalog: every Spec Kit "
                                                        "command that reads the extension catalogs fails")
    assert check.fix == "delete .specify/extension-catalogs.yml (Spec Kit then uses its own catalogs)"
    monkeypatch.setenv("SPECKIT_CATALOG_URL", "https://catalog.example.com/only.json")
    check = check_of(aligned, "catalogs_keep_defaults")
    assert check.status == "ok" and check.message == ("extensions: SPECKIT_CATALOG_URL is set (Spec Kit uses that one "
                                                      "catalog); presets: Spec Kit's own catalogs (no .specify/preset-catalogs.yml)")
    aligned.write(".specify/preset-catalogs.yml", "catalogs: [unclosed\n")
    check = check_of(aligned, "catalogs_keep_defaults")
    assert check.status == "warn" and check.message.startswith("cannot read .specify/preset-catalogs.yml:")


def test_agent_events_wired(aligned: FakeProject, fresh: FakeProject):
    check = check_of(aligned, "agent_events_wired")
    assert check.status == "ok" and check.message == "claude: archiGuard, auditGuard in .claude/settings.json"
    check = check_of(fresh, "agent_events_wired")
    assert check.status == "warn" and check.message == (
        "the agent events of archiGuard, auditGuard are not wired for claude (.claude/settings.json): archiGuard's edit "
        "guard, auditGuard's guard and session records never run")
    # one of the two wired: the other one is named
    fresh.write(".claude/settings.json", '{"hooks": {"PreToolUse": [{"hooks": [{"command": "x speckit.auditguard.guard"}]}]}}')
    assert check_of(fresh, "agent_events_wired").message.startswith("the agent events of archiGuard are not wired for claude")


def test_agent_events_switched_off_overridden_or_not_supported(fresh: FakeProject):
    import json
    fresh.write(".specify/integration.json", json.dumps({"integration": "claude", "installed_integrations": ["claude"],
                                                         "integration_settings": {"claude": {"parsed_options": {"events": "false"}}}}))
    check = check_of(fresh, "agent_events_wired")
    assert check.status == "na" and check.message == "claude: agent events switched off (--events false)"
    fresh.write(".specify/integration.json", json.dumps({"integration": "claude", "installed_integrations": ["claude"],
                                                         "integration_settings": {"claude": {"raw_options": "--events false"}}}))
    assert check_of(fresh, "agent_events_wired").status == "na"
    fresh.write(".specify/integration.json", json.dumps({"installed_integrations": ["claude"]}))
    fresh.write(".specify/integration-events.yml", "integrations:\n  claude:\n    events: {}\n")
    check = check_of(fresh, "agent_events_wired")
    assert check.status == "na" and check.message == "claude: agent events set by .specify/integration-events.yml"
    fresh.write(".specify/integration.json", json.dumps({"installed_integrations": ["windsurf", "copilot"]}))
    check = check_of(fresh, "agent_events_wired")
    assert check.status == "warn" and "not wired for copilot (.github/hooks/speckit.json)" in check.message
    assert "windsurf" not in check.message
    fresh.write(".specify/integration.json", json.dumps({"installed_integrations": ["windsurf"]}))
    check = check_of(fresh, "agent_events_wired")
    assert check.status == "na" and check.message == "windsurf: Spec Kit wires no agent events for it"
    fresh.path(".specify/integration.json").unlink()
    assert check_of(fresh, "agent_events_wired").message == "no integration recorded in .specify/integration.json"


def test_agent_events_of_a_disabled_extension_are_not_expected(fresh: FakeProject):
    import json
    fresh.write(".specify/extensions/.registry", json.dumps({"extensions": {"archiguard": {"enabled": False},
                                                                           "auditguard": {"enabled": False}}}))
    check = check_of(fresh, "agent_events_wired")
    assert check.status == "na" and check.message == "no installed Guardian declares agent events"


def test_preset_missing_while_inline(aligned: FakeProject):
    aligned.remove_preset("archiguard-templates")
    report = verify(aligned)
    check = next(c for c in report.checks if c.id == "preset_matches_integration")
    assert check.status == "fail" and "fell back to hooks" in check.message
    assert report.tools["archiguard"]["effective_integration"] == "hooks"


def test_preset_present_while_hooks(aligned: FakeProject):
    aligned.replace("archiguard", "integration: inline", "integration: hooks")
    assert status_of(verify(aligned), "preset_matches_integration") == "fail"


def test_scopeguard_templates_preset_is_refused(aligned: FakeProject):
    aligned.write(".specify/presets/scopeguard-templates/preset.yml", "preset: {id: scopeguard-templates}\n")
    check = next(c for c in verify(aligned).checks if c.id == "preset_matches_integration")
    assert check.status == "fail" and "specify preset remove scopeguard-templates" in check.fix


def test_versions_in_range(aligned: FakeProject):
    aligned.replace("archiguard", 'version: ">=0.3.0,<0.5"', 'version: ">=0.5.0,<0.6"')
    check = next(c for c in verify(aligned).checks if c.id == "versions_in_range")
    assert check.status == "fail" and f"does not accept scopeGuard {VERSIONS['scopeguard']}" in check.message
    aligned.replace("archiguard", 'version: ">=0.5.0,<0.6"', 'version: ">=0.3.0,<0.5"')
    aligned.replace("auditguard", 'version: ">=0.1,<0.3"', 'version: ">=0.2,<0.3"')
    check = next(c for c in verify(aligned).checks if c.id == "versions_in_range")
    assert check.status == "fail" and "collectors.archiguard.version" in check.message


def test_scopeguard_embedded(aligned: FakeProject):
    aligned.replace("scopeguard", "integration: embedded", "integration: hooks")
    check = next(c for c in verify(aligned).checks if c.id == "scopeguard_embedded")
    assert check.status == "fail" and "integration is hooks" in check.message


def test_scopeguard_embedded_not_applicable_without_the_scope_gate(aligned: FakeProject):
    aligned.write(".specify/extensions/archiguard/NO_SCOPE", "")
    assert status_of(verify(aligned), "scopeguard_embedded") == "na"


def test_auditguard_integration(aligned: FakeProject):
    aligned.replace("auditguard", "integration: hooks", "integration: inline")
    assert status_of(verify(aligned), "auditguard_integration") == "warn"
    aligned.replace("auditguard", "integration: inline", "integration: workflow")
    report = verify(aligned)
    assert status_of(report, "auditguard_integration") == "ok"
    assert status_of(report, "hook_order") == "na"


def test_hook_order(aligned: FakeProject):
    # archiGuard through hooks (preset removed, integration hooks): both tools on after_plan, same priority
    aligned.remove_preset("archiguard-templates")
    aligned.replace("archiguard", "integration: inline", "integration: hooks")
    aligned.write(".specify/extensions.yml", registry_text(lambda ext, ev: ext != "scopeguard", default_priority))
    check = next(c for c in verify(aligned).checks if c.id == "hook_order")
    assert check.status == "fail" and "after_plan" in check.message and "guardians configure" in check.fix
    # with the family priorities the same registry passes
    aligned.write(".specify/extensions.yml", registry_text(
        lambda ext, ev: ext != "scopeguard",
        lambda ext, ev: (1 if ev.startswith("before_") else 90) if ext == "auditguard" else 10))
    check = next(c for c in verify(aligned).checks if c.id == "hook_order")
    assert check.status == "ok" and "shared event" in check.message


def test_hooks_match_integration(aligned: FakeProject):
    aligned.write(".specify/extensions.yml", registry_text(all_enabled, default_priority))
    check = next(c for c in verify(aligned).checks if c.id == "hooks_match_integration")
    assert check.status == "warn" and "scopeGuard: 5 hook(s) enabled but integration embedded" in check.message
    assert "archiGuard: 6 hook(s) enabled but integration inline" in check.message


def test_git_base_agrees(aligned: FakeProject):
    aligned.replace("auditguard", "    base: main", "    base: develop")
    check = next(c for c in verify(aligned).checks if c.id == "git_base_agrees")
    assert check.status == "fail"
    assert check.message == "archiguard git.base=main, auditguard golden.git.base=develop"
    assert "archiguard-config.yml git.base" in check.fix and "a person decides" in check.fix


def test_edit_guard_covers_audit(aligned: FakeProject):
    aligned.replace("archiguard", ', "audit/**", ".specify/extensions/auditguard/**"]', "]")
    check = next(c for c in verify(aligned).checks if c.id == "edit_guard_covers_audit")
    assert check.status == "fail" and "lacks audit/**, .specify/extensions/auditguard/**" in check.message
    aligned.replace("archiguard", "  enabled: true\n  human_only", "  enabled: false\n  human_only")
    check = next(c for c in verify(aligned).checks if c.id == "edit_guard_covers_audit")
    assert check.status == "fail" and "disabled" in check.message


def test_audit_root_moves_the_readonly_paths(aligned: FakeProject):
    aligned.replace("auditguard", "  root: audit ", "  root: trail ")
    aligned.replace("auditguard", 'readonly: ["audit/**", ".specify/extensions/auditguard/**"]', "readonly: []")
    report = verify(aligned)
    check = next(c for c in report.checks if c.id == "edit_guard_covers_audit")
    assert check.status == "fail" and "trail/**" in check.message
    assert status_of(report, "gitattributes") == "warn"


def test_modes_agree(aligned: FakeProject):
    aligned.replace("scopeguard", "mode: enforce", "mode: report")
    check = next(c for c in verify(aligned).checks if c.id == "modes_agree")
    assert check.status == "warn" and check.message.startswith("scopeGuard mode report, archiGuard mode enforce")


def test_gitattributes(aligned: FakeProject):
    aligned.write(".gitattributes", "* text=auto eol=lf\n")
    check = next(c for c in verify(aligned).checks if c.id == "gitattributes")
    assert check.status == "warn" and "3 auditGuard line(s)" in check.message


def test_codeowners(aligned: FakeProject):
    aligned.write(".github/CODEOWNERS", "audit/ @lead\n")
    check = next(c for c in verify(aligned).checks if c.id == "codeowners")
    assert check.status == "warn" and ".specify/standards/" in check.message and "audit/" not in check.message.split("owner for")[1]
    aligned.write(".github/CODEOWNERS", "/.specify/ @lead\n/audit/** @lead\n")
    assert status_of(verify(aligned), "codeowners") == "ok"
    (aligned.root / ".github" / "CODEOWNERS").unlink()
    assert status_of(verify(aligned), "codeowners") == "na"


def test_severity_off_and_warn_from_config(aligned: FakeProject):
    aligned.replace("auditguard", "    base: main", "    base: develop")
    aligned.write(".specify/extensions/guardians/guardians-config.yml", "checks:\n  git_base_agrees: warn\n  codeowners: off\n")
    report = verify(aligned)
    assert status_of(report, "git_base_agrees") == "warn" and status_of(report, "codeowners") == "off"
    assert report.status == "warn" and not report.failed


def test_failed_sibling_status_fails_closed(aligned: FakeProject):
    aligned.write(".specify/extensions/archiguard/FAIL", "3")
    report = verify(aligned)
    check = next(c for c in report.checks if c.id == "scopeguard_embedded")
    assert check.status == "fail" and "cannot tell" in check.message
    assert report.tools["archiguard"]["status_error"].startswith("configure --dry-run exited 3")


def test_two_guardians_only(tmp_path: Path):
    project = make_project(tmp_path / "two", aligned=True, siblings=("archiguard", "auditguard"))
    report = verify(project)
    statuses = {c.id: c.status for c in report.checks}
    assert statuses["installed"] == "fail" and statuses["scopeguard_embedded"] == "na" and statuses["modes_agree"] == "na"
    assert statuses["git_base_agrees"] == "ok" and statuses["edit_guard_covers_audit"] == "ok"


# ----- the CLI ----------------------------------------------------------------------------------------------

def test_cli_verify_text_and_json(aligned: FakeProject, chdir):
    chdir(aligned.root)
    code, out = guardians_cli("verify")
    assert code == 0 and out.startswith(f"Guardians {GUARDIANS_VERSION} | verify |") and "[OK]   installed" in out
    code, out = guardians_cli("verify", "--json")
    import json
    data = json.loads(out)
    assert code == 0 and data["status"] == "ok" and len(data["checks"]) == len(CHECKS) and data["tools"]["guardians"]["version"] == VERSIONS["guardians"]


def test_cli_exit_codes(fresh: FakeProject, chdir, tmp_path: Path):
    chdir(fresh.root)
    code, out = guardians_cli("verify")
    assert code == 1 and "[FAIL] scopeguard_embedded" in out and "RESULT: FAIL" in out
    code, out = guardians_cli("verify", "--root", str(tmp_path / "nowhere"))
    assert code == 2
    fresh.write(".specify/extensions/guardians/guardians-config.yml", "nonsense: 1\n")
    assert guardians_cli("verify")[0] == 2


def test_version_command():
    code, out = guardians_cli("version")
    assert code == 0 and out.strip() == f"Guardians {GUARDIANS_VERSION}"


def test_cross_wiring_fix_names_the_template_when_a_config_is_missing(fresh: FakeProject):
    fresh.config_path("scopeguard").unlink()
    fresh.config_path("archiguard").unlink()
    checks = {c.id: c for c in verify(fresh).checks}
    for check_id, ext in (("scopeguard_embedded", "scopeguard"), ("edit_guard_covers_audit", "archiguard")):
        d = f".specify/extensions/{ext}"
        assert checks[check_id].status == "fail"
        assert checks[check_id].fix.startswith(f"copy {d}/config-template.yml to {d}/{ext}-config.yml, then guardians configure (")


def test_config_hint_follows_the_declared_template(fresh: FakeProject):
    manifest = fresh.path(".specify/extensions/scopeguard/extension.yml")
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "provides:\n  commands: []\n",
        'provides:\n  commands: []\n  config:\n    - { name: "scopeguard-config.yml", template: "templates/sg.yml" }\n'), encoding="utf-8")
    hint = Project(fresh.root).sibling("scopeguard").config_hint()
    assert hint == "copy .specify/extensions/scopeguard/templates/sg.yml to .specify/extensions/scopeguard/scopeguard-config.yml"
