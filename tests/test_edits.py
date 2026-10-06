"""The three line edits, on the siblings' real config templates and on a registry in Spec Kit's dump style."""

from pathlib import Path

import yaml

from conftest import FIXTURES, default_priority, all_enabled, registry_text
from guardians_core.edits import append_to_list, edit_hook_entries, set_top_level_scalar


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ----- set_top_level_scalar --------------------------------------------------------------------------------

def test_integration_line_changes_and_nothing_else():
    text = read("scopeguard-config.yml")
    new, old, changed = set_top_level_scalar(text, "integration", "embedded")
    assert (old, changed) == ("inline", True)
    assert yaml.safe_load(new)["integration"] == "embedded"
    diff = [(a, b) for a, b in zip(text.splitlines(), new.splitlines()) if a != b]
    assert diff == [("integration: inline", "integration: embedded")]
    assert len(text.splitlines()) == len(new.splitlines())


def test_integration_edit_is_idempotent_and_keeps_a_trailing_comment():
    text = "version: 1\nintegration: inline   # how the gates run\nmode: enforce\n"
    new, _, changed = set_top_level_scalar(text, "integration", "embedded")
    assert changed and new == "version: 1\nintegration: embedded   # how the gates run\nmode: enforce\n"
    again, old, changed = set_top_level_scalar(new, "integration", "embedded")
    assert (again, old, changed) == (new, "embedded", False)


def test_missing_key_is_appended_and_an_indented_key_is_not_confused():
    text = "version: 1\nnested:\n  integration: inline\n"
    new, old, changed = set_top_level_scalar(text, "integration", "embedded")
    assert (old, changed) == (None, True)
    assert new.endswith("nested:\n  integration: inline\nintegration: embedded\n")


def test_crlf_files_keep_crlf():
    text = "version: 1\r\nintegration: inline\r\nmode: enforce\r\n"
    new, _, _ = set_top_level_scalar(text, "integration", "embedded")
    assert new == "version: 1\r\nintegration: embedded\r\nmode: enforce\r\n"


# ----- append_to_list ---------------------------------------------------------------------------------------

def test_always_readonly_flow_list_gains_the_audit_paths():
    text = read("archiguard-config.yml")
    new, added = append_to_list(text, "edit_guard", "always_readonly", ["audit/**", ".specify/extensions/auditguard/**"])
    assert added == ["audit/**", ".specify/extensions/auditguard/**"]
    data = yaml.safe_load(new)
    assert data["edit_guard"]["always_readonly"][-2:] == ["audit/**", ".specify/extensions/auditguard/**"]
    assert data["edit_guard"]["always_readonly"][:4] == yaml.safe_load(text)["edit_guard"]["always_readonly"]
    changed = [(a, b) for a, b in zip(text.splitlines(), new.splitlines()) if a != b]
    assert len(changed) == 1 and changed[0][0].lstrip().startswith("always_readonly:")
    assert len(text.splitlines()) == len(new.splitlines())


def test_flow_list_keeps_its_trailing_comment_and_handles_an_empty_list():
    text = "edit_guard:\n  enabled: true\n  always_readonly: []   # none yet\n"
    new, added = append_to_list(text, "edit_guard", "always_readonly", ["audit/**"])
    assert added == ["audit/**"]
    assert new == 'edit_guard:\n  enabled: true\n  always_readonly: ["audit/**"]   # none yet\n'


def test_multi_line_flow_list():
    text = "edit_guard:\n  always_readonly: [\n    \"a/**\",\n    \"b/**\"\n  ]\nfitness: {}\n"
    new, added = append_to_list(text, "edit_guard", "always_readonly", ["audit/**"])
    assert added == ["audit/**"]
    assert yaml.safe_load(new)["edit_guard"]["always_readonly"] == ["a/**", "b/**", "audit/**"]


def test_block_list_gets_new_items_at_the_item_indent():
    text = "edit_guard:\n  enabled: true\n  always_readonly:\n    - \"a/**\"\n    - \"b/**\"\n  after_signoff: []\n"
    new, added = append_to_list(text, "edit_guard", "always_readonly", ["audit/**"])
    assert added == ["audit/**"]
    assert new == "edit_guard:\n  enabled: true\n  always_readonly:\n    - \"a/**\"\n    - \"b/**\"\n    - \"audit/**\"\n  after_signoff: []\n"


def test_missing_key_and_missing_section_are_created():
    text = "edit_guard:\n  enabled: true\nfitness: {}\n"
    new, _ = append_to_list(text, "edit_guard", "always_readonly", ["audit/**"])
    assert yaml.safe_load(new)["edit_guard"] == {"enabled": True, "always_readonly": ["audit/**"]}
    text = "version: 1\n"
    new, _ = append_to_list(text, "edit_guard", "always_readonly", ["audit/**"])
    assert yaml.safe_load(new) == {"version": 1, "edit_guard": {"always_readonly": ["audit/**"]}}


def test_nothing_to_add_changes_nothing():
    text = read("archiguard-config.yml")
    assert append_to_list(text, "edit_guard", "always_readonly", []) == (text, [])


# ----- edit_hook_entries -----------------------------------------------------------------------------------

def family_priority(ext: str, event: str, _cmd: str, current):
    if ext == "auditguard":
        return "1" if event.startswith("before_") else "90"
    if ext in ("scopeguard", "archiguard") and current is None:
        return "10"
    return None


def test_hook_priorities_are_set_only_where_wanted():
    text = registry_text(all_enabled, default_priority)
    new, found = edit_hook_entries(text, "priority", family_priority)
    assert {f["extension"] for f in found} == {"auditguard"}
    assert len(found) == 20
    data = yaml.safe_load(new)
    for event, entries in data["hooks"].items():
        for entry in entries:
            if entry["extension"] == "auditguard":
                assert entry["priority"] == (1 if event.startswith("before_") else 90)
            else:
                assert entry["priority"] == 10
            assert entry["enabled"] is True and "prompt" in entry and "description" in entry
    assert len(new.splitlines()) == len(text.splitlines())


def test_missing_priority_field_is_added_and_other_fields_survive():
    text = registry_text(all_enabled, None)   # Spec Kit always writes priority; an older registry may not
    new, found = edit_hook_entries(text, "priority", family_priority)
    data = yaml.safe_load(new)
    assert len(found) == 20 + 5 + 6
    assert all("priority" in e for entries in data["hooks"].values() for e in entries)
    assert data["hooks"]["after_plan"][0] == {"extension": "scopeguard", "command": "speckit.scopeguard.plan", "priority": 10,
                                              "enabled": True, "optional": False, "prompt": "Execute speckit.scopeguard.plan?",
                                              "description": "(scopeguard) after_plan", "condition": None}


def test_second_pass_changes_nothing():
    text = registry_text(all_enabled, default_priority)
    once, _ = edit_hook_entries(text, "priority", family_priority)
    twice, found = edit_hook_entries(once, "priority", family_priority)
    assert twice == once and found == []


def test_other_sections_and_unknown_extensions_are_untouched():
    text = ("installed:\n- git\n- auditguard\nsettings:\n  auto_execute_hooks: true\nhooks:\n  before_implement:\n"
            "  - extension: git\n    command: speckit.git.commit\n    enabled: true\n    priority: 10\n"
            "  - extension: auditguard\n    command: speckit.auditguard.implemententry\n    enabled: true\n    priority: 10\n"
            "presets: {}\n")
    new, found = edit_hook_entries(text, "priority", family_priority)
    assert [f["command"] for f in found] == ["speckit.auditguard.implemententry"]
    assert "- extension: git\n    command: speckit.git.commit\n    enabled: true\n    priority: 10\n" in new
    assert new.endswith("presets: {}\n")


def test_fixture_registry_parses(tmp_path: Path):
    data = yaml.safe_load(registry_text(all_enabled, default_priority))
    assert set(data["hooks"]) >= {"before_plan", "after_plan", "before_implement", "after_taskstoissues"}
    assert len(data["hooks"]["after_plan"]) == 3
