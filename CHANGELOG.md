# Changelog

All notable changes to Guardians are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). A bundle version is a tested combination of the siblings'
versions; the pins are listed with every release.

## [Unreleased]

Keeps the project's other Spec Kit extensions working next to the Guardians. Pins unchanged.

### Added

- `guardians verify` checks `catalogs_keep_defaults` (warn): a `.specify/extension-catalogs.yml` or
  `preset-catalogs.yml` replaces Spec Kit's catalogs (and a user-level `~/.specify/` file); the check names the
  catalogs such a file hides, an extension file that lists none (every catalog command then fails) and a file that
  cannot be read.
- `guardians verify` checks `agent_events_wired` (warn): for each installed integration that Spec Kit wires agent
  events for (claude, codex, copilot, cursor-agent, devin, gemini, opencode, qwen, tabnine, vibe in Spec Kit 1.1.1),
  the integration's settings file carries archiGuard's and auditGuard's events. Not checked where `--events false`
  or `.specify/integration-events.yml` sets them.
- `guardians configure` repairs both: it appends Spec Kit's `default` (priority 1) and `community` (priority 20,
  discovery only) catalogs to a catalog file whose entries are all family catalogs, exactly as
  `specify ... catalog add` writes them, and it runs `specify extension disable guardians && specify extension
  enable guardians` when the agent events are missing (Spec Kit rewires every enabled extension's events on
  `enable`; Guardians has no hooks or events of its own). A file with other catalogs, a user-level catalog file,
  a dry run, no `specify` on PATH, the `generic` integration or a disabled Guardians get a note instead.

### Changed

- The install instructions (README, bundle README, getting-started guide, `bundle.yml` comment) add Spec Kit's
  `default` and `community` catalogs before the Guardians catalog, for extensions and presets, and give the
  bundle catalog the id `guardians`. The earlier instructions created catalog files with the Guardians entry
  alone, which replaced Spec Kit's catalogs: every other extension of the project disappeared from
  `specify extension search`, `info` and `update` ("not found in catalog") - nothing was uninstalled.
- Uninstall instructions: the three catalog entries, the preset before archiGuard when installed one at a time,
  a catalog file left as `catalogs: []`, and scopeGuard left `embedded` when it was installed before the bundle.
- The getting-started guide: a gate that stops a command skips the other extensions' post-execution hooks (the
  gates now list them under `NOT RUN`); new rows for the two checks and their symptoms.
- Specification amendments A12-A16.

### Fixed

- `configure` keeps the line endings of the files it edits. Spec Kit writes `.specify/extensions.yml` with CRLF on
  Windows; rewritten with LF, `git diff` showed every hook of every other extension removed and added again.

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
