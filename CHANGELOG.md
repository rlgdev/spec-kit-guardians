# Changelog

All notable changes to Guardians are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). A bundle version is a tested combination of the siblings'
versions; the pins are listed with every release.

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
  PowerShell and Python with the family's interpreter search.
- **GitHub Action**: the three siblings' actions (pinned) plus `guardians verify`, each switchable.
- Tests on the siblings' real config templates; an end-to-end run against a real Spec Kit install
  (`tools/e2e-speckit.sh`); `tools/build.py` with pin and version consistency checks and reproducible archives.
