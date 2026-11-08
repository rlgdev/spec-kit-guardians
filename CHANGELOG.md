# Changelog

All notable changes to Guardians are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). A bundle version is a tested combination of the siblings'
versions; the pins are listed with every release.

## [Unreleased]

## [0.2.0] - 2026-11-08

Pins: **scopeGuard 0.5.0** (was 0.4.1) · **archiGuard 0.3.0** (was 0.1.1) · **auditGuard 0.3.0** (was 0.1.0) ·
**archiguard-templates 0.3.0** (was 0.1.1).

Three lines of work that were planned as separate releases (0.1.3 and 0.2.0) ship together: the bundle keeps the
project's other Spec Kit extensions working, pins the scope stamp and the light profile, and checks that the loop
feedback to the domain master design is recorded. `verify` has sixteen checks (was twelve).

### Added

- `guardians verify` checks `catalogs_keep_defaults` (warn): a `.specify/extension-catalogs.yml` or
  `preset-catalogs.yml` replaces Spec Kit's catalogs (and a user-level `~/.specify/` file); the check names the
  catalogs such a file hides or lists as discovery-only, an extension file that lists none (Spec Kit's search,
  update and catalog list then fail) and a file Spec Kit cannot read or refuses.
- `guardians verify` checks `agent_events_wired` (warn): for each installed integration that Spec Kit wires agent
  events for (claude, codex, copilot, cursor-agent, devin, gemini, opencode, qwen, tabnine, vibe in Spec Kit 1.1.1),
  the integration's settings file carries every event of archiGuard and auditGuard that the integration has. Not
  checked where `--events false` or a valid `.specify/integration-events.yml` entry sets them.
- `installed` also fails for a Guardian that is disabled in Spec Kit (`specify extension disable`), and the Tools
  line says so.
- `guardians configure` repairs both: it appends Spec Kit's `default` (priority 1) and `community` (priority 20,
  discovery only) catalogs to a catalog file whose entries are all family catalogs, exactly as
  `specify ... catalog add` writes them, and it runs `specify extension disable guardians`, then
  `specify extension enable guardians`, when the agent events are missing (Spec Kit rewires every enabled
  extension's events on `enable`; Guardians has no hooks or events of its own). It reports only what Spec Kit
  really wired, never leaves Guardians disabled, puts back the bytes of `.specify/extensions.yml` that Spec Kit
  rewrites (comments, line endings), reports a `guardians-config.yml` that `enable` recreated, and leaves a JSON
  settings file with comments alone (Spec Kit cannot merge into it; a note says so). `configure --json` lists the
  notes. A file with other catalogs or a
  user-level catalog file is left alone (`verify` warns with the commands); a dry run lists both repairs under
  `Would change:`; without `specify` on PATH, on the `generic` integration or with Guardians disabled `configure`
  prints the command in a note instead. `checks.<id>: off` turns a check and its repair off.
- `verify` check `scope_stamp` (warn): with scopeGuard 0.5+ and the scope gate in archiGuard's pipeline, the stamp is not
  switched off in archiGuard's `scope-config.yml` and archiGuard's `pipeline.speckit.plan.step_a` runs a `scope` stamp or
  inventory, so the scope of `spec.md` is stamped at hand-over. Not applicable below scopeGuard 0.5.0.
- The getting-started guide explains the stamp: where it is written, what `SCOPE CHANGED AFTER THE STAMP` means and how a
  person re-stamps (`scopeguard stamp --reason`).
- `guardians verify` check `loop_feedback_recorded` (warn): `[OK]` when auditGuard records the feedback archiGuard
  writes. `[WARN]` when auditGuard is older than 0.3.0 or has `collectors.archiguard.feedback: false`. `[--]` when the
  feedback is switched off or archiGuard is older than 0.2.0.
- Getting started: *After coding: the loop feedback* (when it is shown, who it is for, the triage commands).

### Changed

- The install instructions (README, bundle README, getting-started guide, `bundle.yml` comment) add Spec Kit's
  `default` and `community` catalogs before the Guardians catalog, for extensions and presets, and give the
  bundle catalog the id `guardians`. The earlier instructions created catalog files with the Guardians entry
  alone, which replaced Spec Kit's catalogs: every other extension of the project disappeared from
  `specify extension search`, `info` and `update` ("not found in catalog") - nothing was uninstalled.
- Uninstall instructions: archiGuard and auditGuard disabled first (`bundle remove` leaves their agent events
  behind otherwise), the three catalog entries, the preset before archiGuard when installed one at a time, a
  catalog file left as `catalogs: []`, and scopeGuard left `embedded` when it was installed before the bundle.
- The getting-started guide: a gate that stops a command skips the other extensions' post-execution hooks; new
  rows for the two checks and their symptoms.
- Specification amendments A12-A20 (A18 the scope stamp, A19 the loop feedback check, A20 auditGuard's events).
- auditGuard 0.2.0 makes its `light` profile the default: the twenty hooks still record every command, the gate
  verdicts, waivers and decisions, but no agent event runs any more (no session record, no `stop` handler, no
  `pre_tool_use` guard), scopeGuard's report is not re-run at every hook and the views are rebuilt on demand. The
  first field run of the bundle had shown `/speckit.plan` dragging on those events. `profile: full` in
  `auditguard-config.yml` brings the complete recorder back ([auditGuard: Profiles](https://github.com/rlgdev/spec-kit-auditguard#profiles-light-and-full)).
- With auditGuard's own guard off by default, the cross-wiring this bundle has always done - `audit/**` and
  `.specify/extensions/auditguard/**` in archiGuard's `edit_guard.always_readonly` - is the guard on the trail;
  `edit_guard_covers_audit` keeps checking it (`fail`).
- `guardians configure` calls `auditguard configure` as before; in the light profile that call also removes
  auditGuard's switched-off events from the agent's hook config (Claude Code `.claude/settings.json`). A later
  `specify extension add` or `enable` re-wires them; run `guardians configure` again afterwards.
- Pins: scopeGuard 0.5.0 (the scope stamp, the embedded warning), archiGuard 0.3.0 (`archiguard show`, stamps in
  plan step A, keeps the agent away from the stamp file, accepts scopeGuard `<0.6`, the loop feedback),
  auditGuard 0.3.0 (the light profile of 0.2.0, records the stamp and the loop feedback, accepts archiGuard `<0.4`),
  archiguard-templates 0.3.0. The catalogs, the action, the CI refs, the constants Guardians assumes for the siblings
  (`ARCHIGUARD_SCOPE_RANGE`, `ARCHIGUARD_READONLY`, `AUDITGUARD_COLLECTOR_RANGES`) and the test fixtures (the
  siblings' templates at those versions) follow them. `loop_feedback_recorded` expects the feedback from archiGuard
  0.3.0 on (it was planned as 0.2.0, the number `archiguard show` took).

### Fixed

- `configure` and `agent_events_wired` expect auditGuard's agent events only where its configuration switches them on
  (its default `light` profile switches all four off and its own `configure` unwires them); expecting all of them made
  every `guardians configure` re-wire them, so a second run never said `No change needed.` (A20).
- `configure` keeps the line endings of the files it edits (the one most of their lines use). Spec Kit writes
  `.specify/extensions.yml` with CRLF on Windows; rewritten with LF, `git diff` showed every hook of every other
  extension removed and added again.
- A catalog or config file that starts with a byte-order mark is read as Spec Kit reads it.

## [0.1.2] - 2026-10-07

Pins unchanged: scopeGuard 0.4.1 · archiGuard 0.1.1 · auditGuard 0.1.0 · archiguard-templates 0.1.1.

### Changed

- The bundle and the `guardians` extension require Spec Kit 1.0.3 or newer (was 1.0.1). Spec Kit 1.0.1 and 1.0.2 do not
  create the extensions' config files from their templates on `specify bundle install`, so `guardians configure` had
  nothing to cross-wire and `verify` failed; those versions now refuse the bundle before installing anything, with
  "requires Spec Kit >=1.0.3". The siblings' own floors stay at 1.0.1.
- CI: the end-to-end run uses Spec Kit 1.0.3 instead of 1.0.1 next to the latest release, and a `floor` job checks that
  Spec Kit 1.0.2 refuses the bundle.

### Fixed

- `configure` said a missing sibling config file would be created by the sibling's own `configure`; none of the three
  does. The note now names the copy to make (`copy <template> to <config>, then run guardians configure again`, the
  template the sibling's manifest declares), and the `fix:` lines of `scopeguard_embedded` and `edit_guard_covers_audit`
  start with the same copy when the file is missing. Guardians still writes nothing in its place.

## [0.1.1] - 2026-10-07

A bundle for the siblings' patch releases.

Pins: scopeGuard 0.4.1 · archiGuard 0.1.1 · auditGuard 0.1.0 · archiguard-templates 0.1.1.

### Changed

- The bundle, the three catalogs, the composite action and the CI refs pin scopeGuard 0.4.1 and archiGuard 0.1.1
  (the family-consistency, audit and review fixes released as patches); the scopeGuard config fixture is its template
  at `v0.4.1`.
- The getting-started guide: scopeGuard rejects unknown config keys since 0.4.1, so all three tools do; the notes about
  auditGuard and Guardians not being released yet are gone.
- The tests read the Guardians version and the stub siblings' versions from the package and `bundle/bundle.yml`, so a
  pin bump touches only the files `CONTRIBUTING.md` lists.

## [0.1.0] - 2026-10-06

First release: the specification "Guardians bundle for Spec Kit - Specification v1.0"
([docs/specification.md](docs/specification.md)) as a Spec Kit bundle plus a thin extension.

Pins: scopeGuard 0.4.0 · archiGuard 0.1.0 · auditGuard 0.1.0 · archiguard-templates 0.1.0.

### Added

- **Bundle** `guardians` (`bundle/bundle.yml`): the four extensions and the `archiguard-templates` preset at exact
  pins; integration-agnostic; no workflows and no `scopeguard-templates` (archiGuard wraps the commands).
- **Catalogs** for teams: `catalog/extensions.json` (the four extensions), `catalog/presets.json`,
  `catalog/bundles.json` - three `catalog add` commands and one `specify bundle install guardians`.
- **`guardians configure`**: sets scopeGuard to `integration: embedded` when archiGuard runs the scope gate, adds
  auditGuard's read-only paths to archiGuard's `edit_guard.always_readonly`, runs the three siblings' `configure`
  commands in order, gives auditGuard's hooks priority 1 (`before_*`) and 90 (`after_*`) in
  `.specify/extensions.yml`, and ends with the alignment report. Line edits that keep the siblings' comments;
  `--dry-run`; idempotent.
- **`guardians verify`**: twelve checks with configurable severity - installed, preset matches integration,
  versions in range, scopeGuard embedded, auditGuard integration, hook order, hooks match integration, git base
  agrees, edit guard covers the audit trail, modes agree, `.gitattributes`, CODEOWNERS. Exit 1 on a failure;
  `--json`.
- **Agent commands** `/speckit.guardians.configure` and `/speckit.guardians.verify`; launchers for bash,
  PowerShell and Python with the family's interpreter search. The engine never writes `__pycache__` into
  `.specify/extensions/guardians/` (the launcher sets `sys.dont_write_bytecode`), so `git add .specify` stays clean.
- **GitHub Action**: the three siblings' actions (pinned) plus `guardians verify`, each switchable.
- **`tools/check-family.py`**: the consistency check across the four repositories (pins, catalogs, the siblings'
  CI refs, version ranges, fixtures, read-only defaults, launcher parity, the Spec Kit floor, README links);
  CI runs it against the siblings' `main` branches (the fixtures against the templates at the pinned tags).
- **[docs/getting-started.md](docs/getting-started.md)**: the step-by-step guide for a first project, and
  `CONTRIBUTING.md` with the release order of the family; `CODEOWNERS`, `SECURITY.md`, Dependabot.
- Tests on the siblings' real config templates; an end-to-end run against a real Spec Kit install
  (`tools/e2e-speckit.sh`); `tools/build.py` with pin and version consistency checks and reproducible archives.
