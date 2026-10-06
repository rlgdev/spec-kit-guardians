# Guardians bundle for Spec Kit — Specification v1.0 (ready to implement)

> **Status:** implemented in Guardians 0.1.0 (`rlgdev/spec-kit-guardians`), tested against Spec Kit 1.0.1 and 1.0.13
> with scopeGuard 0.4.0, archiGuard 0.1.0 and auditGuard 0.1.0 (main). Where the body below differs, the amendment wins.

## Amendments in the 0.1.0 implementation

| # | Requirement | Amendment | Why |
|---|-------------|-----------|-----|
| A1 | FR-305 | `auditguard_integration` is `[OK]` for both `hooks` and `workflow` (the message says what `workflow` means) and `[WARN]` only for another value. | Both are legitimate choices; a warning on every workflow project would be noise. |
| A2 | FR-306 | `hook_order` is evaluated against auditGuard's **effective** integration (its `configure --dry-run --json`), not the configured one. | Workstation overrides count. |
| A3 | FR-205 | The sibling line is `<Name> : <first line of its own configure output>`; the sibling's line already carries its name and version. | No duplication. |
| A4 | FR-703 | The e2e clones a sibling at its pinned tag and falls back to `main` with a note when the tag does not exist yet (auditGuard until its `v0.1.0`). | CI stays meaningful before the sibling's release and tightens automatically after it. |
| A5 | §5.3 | `checks.<id>: off` must be written as a string (`"off"`); a bare `off` is read as `false` by YAML 1.1 and is accepted as `off` as well. | PyYAML semantics. |
| A6 | FR-702 | The unit tests drive `configure` with **stub** sibling launchers that answer `configure --dry-run --json` the way the real ones do (integration, effective integration, `scope_in_pipeline`, mode) and record the call order; the real siblings are exercised by the e2e only. | Fast, deterministic tests; the contract with the siblings is their JSON, which the stubs reproduce. |
| A7 | FR-205, FR-207 | The changes are listed as a block: a `Changed:` header (`Would change:` with `--dry-run`) followed by one indented `<file>: <what>` line per edit, or `No change needed.` when there is none — not a `changed:`/`would change` prefix on every line. | Matches the `Siblings:`/`Tools:`/`Checks:` blocks of the same report; the unit tests and the e2e assert these exact strings. |
| A8 | §3.4, US3 | A check line is `<mark> <id> <message>` with the mark padded to 6 columns (`[OK]  `, `[WARN]`, `[FAIL]`, `[--]  `) and the id padded to 27, no ` : ` separator; the `fix:` line is indented under the message column. US3's line is `[FAIL] git_base_agrees             archiguard git.base=main, auditguard golden.git.base=develop` and the two file paths are on its `fix:` line. `--json` prints `{"version", "root", "status", "tools", "checks", "notes"}`: top-level `status` is `ok` \| `warn` \| `fail` (a check's additionally `na` or `off`); every `tools` entry carries `installed` (an absent sibling is `{"installed": false}`), an installed one adds `version` and, except `guardians`, `integration`, `effective_integration`, `mode`, `hooks_on`, `hooks`, plus `status_error` when its `configure --dry-run --json` could not be read and, for `archiguard`, `scope_in_pipeline` and `preset`; `notes` is a list of strings (empty in this version). | Aligned columns: the message starts where the longest id ends; the JSON carries what the text report shows. |
| A9 | FR-313, §5.5 | A tools line is `<Name padded to 10> : <version> \| integration <configured>[ -> <effective>] \| mode <mode> \| hooks <on>/<registered>`; archiGuard's line adds `\| scope gate in pipeline` / `\| scope gate not in pipeline` (when its JSON carries `scope_in_pipeline`) and `\| preset installed` / `\| preset missing`; Guardians' own line is `Guardians  : <version>`; an absent Guardian prints `<Name> : not installed`. `integration`, `effective_integration`, `mode` and `scope_in_pipeline` come from the sibling's `configure --dry-run --json` (a key that JSON does not print, such as archiGuard's `mode`, from its config file); the hook counts come from `.specify/extensions.yml` (entries with `extension: <id>`, enabled unless `enabled: false`); the JSON's `hooks[]` and `readiness` are not read. | Same shape as the configure sibling line (A3); the archiGuard facts the checks use are shown where they come from. |

| | |
|---|---|
| Bundle id | `guardians` · repository `rlgdev/spec-kit-guardians` · MIT |
| Extension id | `guardians` — the thin fourth extension that configures and verifies the family |
| Family | Guardians — scopeGuard (0.4.x), archiGuard (0.1.x), auditGuard (0.1.x); this bundle is their one cover |
| Host | GitHub Spec Kit ≥ 1.0.1 (`specify bundle` since 0.11.4, hook `priority` since 0.10.0; archiGuard and auditGuard need 1.0.1) · Python ≥ 3.9, standard library (YAML through PyYAML or a sibling's reader, D3) |
| Traceability | User stories `US1–US5`, functional requirements `FR-###`, non-functional `NFR-###`, success criteria `SC-###` |

---

## 0. Summary and decisions

### 0.1 What the bundle delivers

One `specify bundle install guardians` installs the three Guardians and their preset at tested, pinned
versions; one `/speckit.guardians.configure` runs their three `configure` commands in the right order,
applies the cross-wiring the three tools document as required but cannot do for each other, orders the
hooks they share, and prints one table of what is in force; one `guardians verify` (locally and in CI)
fails when the three configurations disagree. Nothing else changes: each Guardian keeps its own engine,
config file, release cadence and documentation.

### 0.2 Decisions taken

| # | Decision | Taken |
|---|----------|-------|
| D1 | Composition | A Spec Kit **bundle** with four extensions (`scopeguard`, `archiguard`, `auditguard`, `guardians`) and one preset (`archiguard-templates`). No workflows (the siblings publish no workflow catalog; `integration: workflow` users add `scopeguard-sdd` / `archiguard-sdd` by hand). No `scopeguard-templates` preset (archiGuard wraps the commands and runs the scope gate itself). |
| D2 | Configuration model | **Align and verify.** The three config files stay authoritative. `guardians configure` runs the three configures and applies only the cross-wiring each tool's own documentation calls for: scopeGuard `integration: embedded` under archiGuard, archiGuard's edit guard covering the audit trail, hook order. Values one tool owns alone (git base, mode, budgets) are **compared, never written**. |
| D3 | Interface to the siblings | Their **command lines** (`configure --dry-run --json`) and their **config files**; never their Python modules. One exception: reading YAML uses PyYAML when importable, else the `yamlio` reader of the installed auditGuard or archiGuard (the bundle installs them), else a clear error. Edits are line-based and keep the siblings' comments. |
| D4 | Hook order (family convention) | On a shared event auditGuard records **first** (`before_*`, priority 1) and **last** (`after_*`, priority 90); the gates keep Spec Kit's default 10. `configure` writes the priorities into `.specify/extensions.yml`; `verify` checks them. A sibling reinstall re-registers its hooks with its manifest priorities; `configure` re-applies. |
| D5 | Distribution | Three catalogs in this repository: `catalog/extensions.json` (the four extensions, versions equal to the pins), `catalog/presets.json` (`archiguard-templates`), `catalog/bundles.json` (the bundle). Release assets `guardians.zip` (extension), `guardians-bundle.zip` (bundle artefact), `SHA256SUMS`. Bundle pins must be exact versions; a pin resolves only through an install-allowed catalog whose entry carries that version. |
| D6 | Layout | Extension files at the repository root (as the siblings; `specify extension add --dev <repo>` works); the bundle manifest in `bundle/` (`bundle.yml` + `README.md` — exactly what `specify bundle build` packs). |
| D7 | CI | One composite action that runs the three siblings' own actions (pinned) and `guardians verify`; each part can be switched off. |
| D8 | Naming | Ids `guardians` (`speckit.guardians.configure`); the local folder name is free. Renaming before the first release touches six files; `tools/build.py --check` fails when the ids or versions disagree. |

### 0.3 Prerequisites outside this repository

- auditGuard must have a GitHub release `v0.1.0` with `auditguard.zip` attached (scopeGuard `v0.4.0` and
  archiGuard `v0.1.0` exist). Until then `bundle install` fails downloading `auditguard`; the e2e test
  installs the siblings from checkouts and does not depend on it.
- `guardians` itself must be released (`v0.1.0`, `guardians.zip`, `guardians-bundle.zip`) before the
  catalogs resolve.

---

## 1. Scope, actors, glossary

**In scope.** The bundle manifest and its README; the three catalogs; the `guardians` extension (CLI
`configure`, `verify`, `version`; two agent commands; config template; launchers for bash, PowerShell
and Python); the GitHub Action; tests, an e2e against a real Spec Kit install, build and release tooling;
documentation.

**Out of scope.** Changing a sibling's engine, manifest or config schema; a user interface; generating
the siblings' configs from one file (option 2, rejected); workflows; Jira or other integrations.

**Actors.** *Lead architect* — installs and configures the family, owns the pins. *Developer* — runs
`/speckit.guardians.configure` after cloning. *Agent* — runs the two commands when asked; never edits a
sibling's config beyond what the script did. *CI* — runs the action as a required check.

**Glossary.** *Pin* — the exact sibling version a bundle release was tested with. *Cross-wiring* — a
setting in one Guardian's config whose only purpose is another Guardian (D2). *Alignment* — the shared
keys agree (§3.4). *Effective integration* — what a sibling's `configure --json` reports after its local
overrides and fallbacks (archiGuard falls back from `inline` to `hooks` without its preset).

---

## 2. User stories

Priorities: P1 ships in 0.1.0, P2 in 0.1.x.

### US1 — Install the family in one step (P1)
As a lead architect, I want one install command for scopeGuard, archiGuard, auditGuard and their preset
at versions tested together, so that every project of my teams starts from the same stack.

*Acceptance.* **Given** a Spec Kit project with the three Guardians catalogs added, **when**
`specify bundle install guardians`, **then** `specify extension list` shows the four extensions at the
pinned versions, `specify preset list` shows `archiguard-templates`, and `specify bundle list` shows
`guardians`.

### US2 — Configure the family in one step (P1)
As a developer, I want one command that configures all three tools consistently, so that I do not read
three READMEs to learn that scopeGuard must be `embedded` and the edit guard must cover `audit/`.

*Acceptance.* **Given** the bundle is installed with default configs, **when**
`/speckit.guardians.configure` runs, **then** scopeGuard's config says `integration: embedded`,
archiGuard's `edit_guard.always_readonly` contains `audit/**` and `.specify/extensions/auditguard/**`,
auditGuard's `before_*` hooks carry priority 1 and `after_*` 90 in `.specify/extensions.yml`, the three
configures ran in order, and one table shows integration, mode, hooks and versions per tool with
`[OK]` on every check. A second run changes nothing.

### US3 — See where the three disagree (P1)
As a lead architect, I want a check that names every disagreement between the three configurations with
the file, the key and the fix, so that a wrong `git.base` or a missing preset is found before the gates
run.

*Acceptance.* **Given** archiGuard `git.base: main` and auditGuard `golden.git.base: develop`, **when**
`guardians verify` runs, **then** it prints `[FAIL] git_base_agrees             archiguard git.base=main,
auditguard golden.git.base=develop` with both file paths and exits `1`.

### US4 — One required check in CI (P2)
As a developer, I want one action in the pipeline that runs the three gates' CI checks and the alignment
check, so that the workflow file has one step for governance.

### US5 — Upgrade the family (P2)
As a lead architect, I want to move a project to the next tested combination by bumping one bundle
version, and be told when a sibling's version falls outside what its neighbours support.

---

## 3. Functional requirements

### 3.1 Bundle and catalogs (FR-0xx)

- **FR-001** `bundle/bundle.yml` SHALL declare schema `1.0`, bundle `guardians` with the repository's
  version, role `architect`, `requires.speckit_version: ">=1.0.1"`, no `integration` (the bundle inherits
  the project's), and `provides`: extensions `scopeguard 0.4.0`, `archiguard 0.1.0`, `auditguard 0.1.0`,
  `guardians <version>` (exact pins; §5.1), preset `archiguard-templates 0.1.0` with `priority: 10` and
  `strategy: wrap` (the bundle-level strategy is required by the schema; the preset's own per-entry
  strategies apply at install).
- **FR-002** `bundle/README.md` SHALL state what is installed, the three catalog commands, the install
  command, the configure command and the two notes of FR-004.
- **FR-003** Catalogs: `catalog/extensions.json` SHALL list the four extensions with `version` equal to
  the pins and `download_url` of the siblings' release assets
  (`https://github.com/rlgdev/spec-kit-<id>/releases/download/v<version>/<id>.zip`);
  `catalog/presets.json` SHALL list `archiguard-templates`; `catalog/bundles.json` SHALL list `guardians`
  with `download_url` `https://github.com/rlgdev/spec-kit-guardians/releases/download/v<version>/guardians-bundle.zip`,
  `provides` counts and `verified: false`. All three carry `catalog_url` pointing at their raw file on
  `main`.
- **FR-004** The documented install (README, bundle README) is:
  ```bash
  specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/extensions.json --name guardians --install-allowed
  specify preset catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/presets.json    --name guardians --install-allowed
  specify bundle catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/bundles.json
  specify bundle install guardians
  bash .specify/extensions/guardians/scripts/bash/guardians.sh configure   # or /speckit.guardians.configure
  ```
  with two notes: a project-scoped extension catalog replaces Spec Kit's built-in catalogs for that
  project (first-party extensions still install from the package); an extension already installed outside
  the bundle must be at the pinned version or `bundle install` stops before changing anything.
- **FR-005** `tools/build.py --check` SHALL fail when the version differs between `extension.yml`,
  `guardians_core/__init__.py`, `bundle/bundle.yml` (bundle version and the `guardians` pin) and the
  three catalogs; when a sibling pin in `bundle.yml` differs from its catalog version; when the bundle
  README is missing; or when an id appears that is not `guardians`.

### 3.2 The `guardians` extension (FR-1xx)

- **FR-101** `extension.yml` (§5.2): id `guardians`, two commands `speckit.guardians.configure` and
  `speckit.guardians.verify`, one config template, no hooks, no events, `category: process`,
  `effect: read-write` (it writes only `.specify/extensions.yml` priorities, scopeGuard's `integration`
  and archiGuard's `edit_guard.always_readonly`, FR-2xx).
- **FR-102** CLI (§5.4): `guardians configure [--dry-run] [--no-siblings]`, `guardians verify`,
  `guardians version`; every command accepts `--root DIR` (default: the nearest ancestor with
  `.specify/`), `--config FILE`, `--json`, `--verbose`.
- **FR-103** Launchers `scripts/bash/guardians.sh`, `scripts/powershell/guardians.ps1`,
  `scripts/python/guardians.py` with the siblings' interpreter search (`GUARDIANS_PYTHON`, `python3` /
  `python` skipping the Windows Store stub, specify-cli's Python under `uv tool dir`, `uv run`).
- **FR-104** Sibling discovery: a sibling is *installed* when `.specify/extensions/<id>/extension.yml`
  exists; its version is read from that file; its launcher is `.specify/extensions/<id>/scripts/python/<id>.py`
  run with the interpreter running guardians (no second interpreter search). The preset is installed when
  `.specify/presets/<preset-id>/` exists.
- **FR-105** Exit codes: `0` ok; `1` `verify` found a `fail` (also `configure`, when a `fail` remains
  after it ran); `2` cannot run (no project root, config error, a sibling's configure exited non-zero, a
  file would not parse after an edit).

### 3.3 `configure` (FR-2xx)

Order of work: cross-wiring (FR-202, FR-203) **before** the siblings' configures, so that scopeGuard's
configure already sees `embedded`; then the three configures (FR-201); then hook order (FR-204); then the
report (FR-205).

- **FR-201 siblings.** For each id in `order` (default `scopeguard, archiguard, auditguard`) that is
  installed, run `<launcher> configure` (`--dry-run` passed through) with cwd = project root and the same
  interpreter. Print the sibling's first output line (full output with `--verbose`). A non-zero exit
  prints the sibling's output and stops with exit `2`. `--no-siblings` skips this step.
- **FR-202 scopeGuard embedded.** When archiGuard and scopeGuard are installed, archiGuard's
  `configure --dry-run --json` reports `scope_in_pipeline: true`, scopeGuard's version satisfies
  `>=0.4.0` and `scopeguard-config.yml` does not say `integration: embedded`: rewrite the top-level
  `integration:` line to `embedded` (comments and the rest of the file untouched). Missing config file →
  note, no change (the sibling's `configure` scaffolds it).
- **FR-203 edit guard covers the trail.** When archiGuard and auditGuard are installed: the paths of
  auditGuard's `guard.readonly` (default `audit/**`, `.specify/extensions/auditguard/**`, read from
  `auditguard-config.yml`, defaults when absent, `audit` replaced by `audit.root` when set) that are not in
  archiGuard's `edit_guard.always_readonly` are appended to that flow list in `archiguard-config.yml`
  (one-line flow list edit; a block list is edited by appending `- "<path>"` items at the list's indent).
- **FR-204 hook order.** In `.specify/extensions.yml`, for every hook entry whose `extension` is a
  Guardian: auditGuard `before_*` entries get `priority: <hook_priority.auditguard.before>` (1),
  `after_*` entries `<hook_priority.auditguard.after>` (90); scopeGuard and archiGuard entries get
  `<hook_priority.default>` (10) only when they carry no `priority`. The edit is line-based (the shape of
  the siblings' `set_hook_flags`), preserves every other field and comment, and is refused (exit `2`)
  when the result does not parse.
- **FR-205 report.** After the work, `configure` prints: a header `Guardians <version> | configure[ (dry
  run)] | <root>`, one line per sibling (`<name> <version> | configure | <its first line>`), the list of
  changes (`changed: <file>: <what>` or `would change:`), then the full `verify` report (§3.4). Exit `1`
  when the report has a `fail`.
- **FR-206 idempotence.** A second `configure` on an unchanged project reports no change.
- **FR-207 dry run.** `--dry-run` passes to the siblings and turns every edit into a `would change` line.

### 3.4 `verify` (FR-3xx)

Each check has an id, a severity from the config (`fail` | `warn` | `off`, defaults below), a message and
a fix (a command or a file + key). Output: one line per check `[OK]`/`[WARN]`/`[FAIL]`/`[--]` (off or not
applicable) `<id> : <message>` and, for WARN and FAIL, an indented `fix: …`. `--json` prints
`{"version", "root", "tools": {...}, "checks": [{"id", "severity", "status", "message", "fix"}], "status"}`.
Exit `1` when any check is `FAIL`.

- **FR-301 `installed`** (fail) — the four extensions are installed. Fix: `specify bundle install guardians`.
- **FR-302 `preset_matches_integration`** (fail) — `archiguard-templates` is installed when archiGuard's
  effective integration is `inline`, and archiGuard's config does not say `inline` while the preset is
  missing (archiGuard then silently falls back to hooks). `scopeguard-templates` is not installed.
- **FR-303 `versions_in_range`** (fail) — scopeGuard's version satisfies archiGuard's
  `gates.scope.version`; scopeGuard's and archiGuard's versions satisfy auditGuard's
  `collectors.scopeguard.version` and `collectors.archiguard.version`. The specifier syntax is the
  siblings' (`>=a,<b`, `==`, `!=`, `~=`).
- **FR-304 `scopeguard_embedded`** (fail) — scopeGuard `integration` is `embedded` when archiGuard's
  pipeline runs the scope gate (`scope_in_pipeline`). Fix: `guardians configure`.
- **FR-305 `auditguard_integration`** (warn) — auditGuard integration is `hooks` or `workflow`; `hooks`
  is reported as recommended with the inline gates (`workflow` records through the siblings' workflows only).
- **FR-306 `hook_order`** (fail when auditGuard integration is `hooks`, else `--`) — for every event with
  more than one enabled Guardian hook in `.specify/extensions.yml`, every enabled auditGuard `before_*`
  entry has a lower priority than every other Guardian's entry on that event and every enabled auditGuard
  `after_*` entry a higher one. Fix: `guardians configure`.
- **FR-307 `hooks_match_integration`** (warn) — enabled scopeGuard hooks exist only when scopeGuard's
  effective integration is `hooks`; enabled archiGuard hooks only when archiGuard's is `hooks`; enabled
  auditGuard hooks only when auditGuard's is `hooks`. Fix: `<sibling> configure`.
- **FR-308 `git_base_agrees`** (fail) — archiGuard `git.base` equals auditGuard `golden.git.base` (both
  default `main`). Fix: the two file paths and keys; a person decides which is right.
- **FR-309 `edit_guard_covers_audit`** (fail) — archiGuard `edit_guard.enabled` is true and
  `always_readonly` contains every auditGuard readonly path (FR-203). Fix: `guardians configure`.
- **FR-310 `modes_agree`** (warn) — scopeGuard `mode` equals archiGuard `mode` (`enforce` | `report`);
  auditGuard's `mode` (`record` | `enforce`) is reported, not compared (different meaning).
- **FR-311 `gitattributes`** (warn) — `.gitattributes` has auditGuard's three lines
  (`<audit>/**/*.jsonl -text`, `<audit>/**/evidence/** -text`, `<audit>/**/seal.json -text`). Fix:
  `auditguard configure`.
- **FR-312 `codeowners`** (warn) — when a `CODEOWNERS` file exists (`.github/CODEOWNERS`, `CODEOWNERS`,
  `docs/CODEOWNERS`), it has a rule whose pattern covers each of `<audit>/`, `.specify/standards/`,
  `.specify/archiguard/`, `.specify/extensions/` (prefix match on the rule's pattern); without a
  CODEOWNERS file the check is `[--]` with a one-line hint.
- **FR-313 tools table.** Before the checks, `verify` prints one line per Guardian:
  `<name> <version> | integration <configured>[ -> <effective>] | mode <mode> | hooks <on>/<registered>`
  with `not installed` when absent; values come from the sibling's `configure --dry-run --json`
  (`integration`, `effective_integration`, `mode`, `scope_in_pipeline`, each when that sibling prints it; §5.5)
  and, for keys
  that JSON does not carry (`git.base`, `edit_guard.*`, `gates.scope.version`, `golden.git.base`,
  `guard.readonly`, `collectors.*.version`, `audit.root`), from the config files (§5.5).
- **FR-314** `verify` never writes.

### 3.5 Agent commands (FR-4xx)

- **FR-401** `commands/speckit.guardians.configure.md`: run `{SCRIPT}` from the repository root, show the
  output as is; when a `[FAIL]` names a decision for a person (`git_base_agrees`), tell the user which two
  files disagree and stop; never edit a sibling's config or `.specify/extensions.yml` yourself.
- **FR-402** `commands/speckit.guardians.verify.md`: run `{SCRIPT}`, show the output, exit code `0` =
  aligned, `1` = findings; quote each `fix:` line.
- **FR-403** Command frontmatter uses the three `scripts` keys (`sh`, `ps`, `py`) with extension-relative
  paths, as the siblings.

### 3.6 Configuration (FR-5xx)

- **FR-501** `.specify/extensions/guardians/guardians-config.yml` (§5.3) scaffolded from
  `config-template.yml` by Spec Kit; optional — defaults apply when absent; unknown keys are errors
  (exit `2`).
- **FR-502** Keys: `version: 1`; `order` (list of sibling ids); `hook_priority` (`auditguard.before`,
  `auditguard.after`, `default`, integers ≥ 1); `checks` (check id → `fail` | `warn` | `off`).

### 3.7 GitHub Action (FR-6xx)

- **FR-601** `action.yml` (composite): inputs `scopeguard`, `archiguard`, `auditguard`, `verify` (each
  `"true"` | `"false"`, default `"true"`), `working-directory` (`.`), `features` (`all`, passed to the
  gates), `auditguard-golden` (`"true"`). Steps: `rlgdev/spec-kit-scopeguard@v0.4.0` (command `check`),
  `rlgdev/spec-kit-archiguard@v0.1.0`, `rlgdev/spec-kit-auditguard@v0.1.0` (command `verify`), each
  guarded by its input; then `guardians verify` run with the installed engine
  (`.specify/extensions/guardians/scripts/python/guardians.py`), falling back to the action's own.
- **FR-602** The sibling action versions are the bundle pins; `tools/build.py --check` fails when they differ.

### 3.8 Packaging, tests, release (FR-7xx)

- **FR-701** `tools/build.py` builds `dist/guardians.zip` (extension files: `extension.yml`,
  `config-template.yml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `commands/`, `scripts/`),
  `dist/guardians-bundle.zip` (`bundle/bundle.yml`, `bundle/README.md` at the archive root, as
  `specify bundle build` would) and `dist/SHA256SUMS`; reproducible (fixed timestamps, sorted entries,
  normalised modes); `--check`, `--check-tag vX.Y.Z` as the siblings.
- **FR-702** Tests (`pytest`, standard library): config loading and defaults; the three line edits on the
  siblings' real templates (fixtures copied from their repositories at the pinned tags); hook priority
  edit on a registry fixture with three extensions; `verify` on fixture projects (aligned → 0; each
  disagreement → the named check fails); `configure` on a fixture project with stub sibling launchers
  (order, dry run, idempotence, a failing sibling → exit 2); launchers; build `--check`.
- **FR-703** `tools/e2e-speckit.sh`: `specify init`; `specify extension add --dev` of the three siblings
  (checkouts at the pinned tags, `SCOPEGUARD_SRC`, `ARCHIGUARD_SRC`, `AUDITGUARD_SRC`) and of this
  repository; `specify preset add --dev <archiguard>/preset`; `guardians verify` → exit `1`
  (`scopeguard_embedded`, `edit_guard_covers_audit`); `guardians configure` → exit `0`, the three files
  changed as US2; `guardians verify` → `0`; change auditGuard's `golden.git.base` → `verify` exits `1`
  naming `git_base_agrees`; `specify bundle validate --path bundle --offline` passes (warnings allowed);
  `specify bundle install ./bundle/bundle.yml --offline` reports the components as already present (every
  pin equals the installed version) — skipped with a note on Spec Kit versions that refuse.
- **FR-704** CI (`.github/workflows/ci.yml`): tests on ubuntu/windows/macos × Python 3.9/3.13; lint
  (pyflakes, shellcheck, `build.py --check`); launchers; e2e against `specify-cli` latest and `1.0.1`;
  action self-test on a fixture project (verify passes, then a tampered `git.base` fails); `family`
  (`tools/check-family.py` against the siblings' `main` branches, the fixtures against the config templates at the
  pinned tags; a tag that does not exist yet is compared with `main`).
- **FR-705** Release (`release.yml`): on tag `vX.Y.Z`, tests, `build.py --check-tag`, release with the
  three assets and the CHANGELOG section as notes.

---

## 4. Non-functional requirements

- **NFR-001 Dependencies.** Python ≥ 3.9 standard library; YAML through PyYAML when present, else the
  installed siblings' reader (D3); no network.
- **NFR-002 Never changes an engine.** guardians writes nothing under a sibling's `scripts/`, `commands/`
  or `extension.yml`; its three edits are listed in FR-101.
- **NFR-003 Idempotent and reversible.** Every edit is a line change a person can read in `git diff`;
  `--dry-run` shows it first.
- **NFR-004 Time.** `configure` ≤ 10 s with the three siblings (three subprocesses plus three dry-run
  JSON calls); `verify` ≤ 5 s.
- **NFR-005 Portability.** Windows (PowerShell launcher, paths with `!`), macOS, Linux; LF in written files.
- **NFR-006 Fail-closed verification.** `verify` reports `FAIL` whenever it cannot establish a check it
  was asked to make (unreadable config, sibling JSON missing) and says why.
- **NFR-007 Size.** The extension stays under 1 500 lines of Python.

---

## 5. Data contracts

### 5.1 `bundle/bundle.yml`

```yaml
schema_version: "1.0"

bundle:
  id: "guardians"
  name: "Guardians"
  version: "0.1.0"
  role: "architect"
  description: "scopeGuard, archiGuard and auditGuard at tested versions, with one configure and one alignment check: scope, architecture and audit-trail governance for the Spec Kit SDLC"
  author: "rlgdev"
  license: "MIT"

requires:
  speckit_version: ">=1.0.1"
  tools: ["python>=3.9", "git>=2.20"]
  mcp: []

provides:
  extensions:
    - { id: "scopeguard", version: "0.4.0" }
    - { id: "archiguard", version: "0.1.0" }
    - { id: "auditguard", version: "0.1.0" }
    - { id: "guardians",  version: "0.1.0" }
  presets:
    - { id: "archiguard-templates", version: "0.1.0", priority: 10, strategy: "wrap" }

tags: ["governance", "architecture", "scope", "audit", "quality-gate"]
```

### 5.2 `extension.yml`

```yaml
schema_version: "1.0"
extension:
  id: guardians
  name: "Guardians"
  version: "0.1.0"
  description: "One cover for scopeGuard, archiGuard and auditGuard: configures the three in order, cross-wires what each needs from the others, orders their hooks and verifies that their configurations agree"
  author: "rlgdev"
  repository: https://github.com/rlgdev/spec-kit-guardians
  homepage: https://github.com/rlgdev/spec-kit-guardians
  license: MIT
  category: process
  effect: read-write
requires:
  speckit_version: ">=1.0.1"
  tools:
    - { name: python, version: ">=3.9", required: false, description: "Runs the configurator (standard library; YAML through PyYAML or a sibling's reader). Without python on PATH the launchers use specify-cli's Python, or uv." }
provides:
  commands:
    - { name: speckit.guardians.configure, file: commands/speckit.guardians.configure.md, description: "Configure scopeGuard, archiGuard and auditGuard together: run their configures in order, cross-wire them, order their hooks, show what is in force" }
    - { name: speckit.guardians.verify,    file: commands/speckit.guardians.verify.md,    description: "Check that the three Guardians' configurations agree (versions, integration, hook order, git base, edit guard, CODEOWNERS)" }
  config:
    - { name: "guardians-config.yml", template: "config-template.yml", description: "Configure order, hook priorities, check severities", required: false }
tags: ["governance", "architecture", "scope", "audit", "quality-gate"]
```

### 5.3 `config-template.yml`

```yaml
# Guardians configuration (optional - these are the defaults)
# Location: .specify/extensions/guardians/guardians-config.yml
version: 1

order: [scopeguard, archiguard, auditguard]   # the siblings' configure commands run in this order

hook_priority:                 # .specify/extensions.yml - lower runs first; Spec Kit's default is 10
  auditguard: { before: 1, after: 90 }        # auditGuard records first and last on a shared event
  default: 10                                 # gates keep Spec Kit's default (set only when missing)

checks:                        # fail | warn | off
  installed: fail
  preset_matches_integration: fail
  versions_in_range: fail
  scopeguard_embedded: fail
  auditguard_integration: warn
  hook_order: fail
  hooks_match_integration: warn
  git_base_agrees: fail
  edit_guard_covers_audit: fail
  modes_agree: warn
  gitattributes: warn
  codeowners: warn
```

### 5.4 CLI

```text
guardians configure [--dry-run] [--no-siblings] [--root DIR] [--config FILE] [--json] [--verbose]
guardians verify    [--root DIR] [--config FILE] [--json] [--verbose]
guardians version
```

### 5.5 What `verify` reads

| Source | Keys |
|--------|------|
| `.specify/extensions/<id>/extension.yml` | `extension.version` (regex) |
| `<id> configure --dry-run --json` | `integration`, `effective_integration` (scopeGuard, archiGuard; auditGuard prints none and its `integration` is used), `mode` (scopeGuard, auditGuard; archiGuard's from its config file), `scope_in_pipeline` (archiGuard) |
| `scopeguard-config.yml` | `integration`, `mode` |
| `archiguard-config.yml` | `integration`, `mode`, `git.base`, `edit_guard.enabled`, `edit_guard.always_readonly`, `gates.scope.version` |
| `auditguard-config.yml` | `integration`, `mode`, `audit.root`, `golden.git.base`, `guard.readonly`, `collectors.scopeguard.version`, `collectors.archiguard.version` |
| `.specify/extensions.yml` | `hooks.<event>[]` entries: `extension`, `command`, `enabled`, `priority` |
| `.specify/presets/<id>/` | presence |
| `.gitattributes`, `CODEOWNERS` | lines |

### 5.6 `verify --json`

```json
{"version": "0.1.0", "root": "/path/to/project", "status": "fail",
 "tools": {"scopeguard": {"installed": true, "version": "0.4.0", "integration": "embedded", "effective_integration": "embedded", "mode": "enforce", "hooks_on": 0, "hooks": 5},
           "archiguard": {"installed": true, "version": "0.1.0", "integration": "inline", "effective_integration": "inline", "mode": "enforce", "hooks_on": 0, "hooks": 6, "scope_in_pipeline": true, "preset": true},
           "auditguard": {"installed": true, "version": "0.1.0", "integration": "hooks", "effective_integration": "hooks", "mode": "record", "hooks_on": 20, "hooks": 20},
           "guardians":  {"installed": true, "version": "0.1.0"}},
 "checks": [{"id": "git_base_agrees", "severity": "fail", "status": "fail",
             "message": "archiguard git.base=main, auditguard golden.git.base=develop",
             "fix": ".specify/extensions/archiguard/archiguard-config.yml git.base / .specify/extensions/auditguard/auditguard-config.yml golden.git.base - a person decides which is right"}],
 "notes": []}
```

---

## 6. Repository, modules, tests, release

### 6.1 Layout

```text
spec-kit-guardians/
  extension.yml  config-template.yml  README.md  CHANGELOG.md  CONTRIBUTING.md  SECURITY.md  LICENSE  action.yml  .extensionignore  .gitattributes  .gitignore  pytest.ini
  bundle/bundle.yml  bundle/README.md
  catalog/extensions.json  catalog/presets.json  catalog/bundles.json
  commands/speckit.guardians.configure.md  commands/speckit.guardians.verify.md
  scripts/bash/guardians.sh  scripts/powershell/guardians.ps1  scripts/python/guardians.py
  scripts/python/guardians_core/
    __init__.py   version
    cli.py        argument parsing, exit codes, output
    common.py     project root, read/write text (LF), version_satisfies, GuardiansError
    yamlio.py     PyYAML or a sibling's reader (D3)
    siblings.py   discovery, versions, launchers, `configure --dry-run --json`
    edits.py      the three line edits (integration line, always_readonly list, hook priorities)
    configure.py  FR-2xx
    verify.py     FR-3xx
  tests/  conftest.py (fake project, stub sibling launchers, a registry in Spec Kit's dump style, CODEOWNERS)  fixtures/ (the siblings' config templates at the pins)  test_config_and_yaml.py  test_edits.py  test_verify.py  test_configure.py  test_build_and_launchers.py
  tools/build.py  tools/check-family.py  tools/e2e-speckit.sh
  docs/specification.md  docs/getting-started.md
  .github/workflows/ci.yml  release.yml  .github/CODEOWNERS  .github/dependabot.yml
```

### 6.2 Implementation order

1. `common`, `yamlio`, `siblings`, `edits` with tests on the real sibling templates. 2. `verify`.
3. `configure`. 4. Launchers, commands, config template, `build.py`, catalogs, bundle. 5. Action, e2e,
CI, release, README, CHANGELOG.

### 6.3 Release conventions

Same as the siblings: version in `extension.yml`, `guardians_core/__init__.py`, `bundle/bundle.yml`
(twice), the three catalogs and the sibling action pins in `action.yml`; a CHANGELOG entry; tag
`vX.Y.Z`; the release workflow attaches `guardians.zip`, `guardians-bundle.zip`, `SHA256SUMS`. A new
sibling version means: bump its pin and catalog entry, run the e2e against the new tag, release a new
bundle version.

---

## 7. Success criteria

- **SC-001** In the e2e, after `bundle install` (or the `--dev` equivalent) and one `configure`, `verify`
  exits `0` with `[OK]` on all twelve checks, and the three files of US2 show exactly the expected lines in
  `git diff`.
- **SC-002** Each of the twelve checks is made to fail by one fixture change and is reported by name with
  the fix (one test per check).
- **SC-003** Two consecutive `configure` runs: the second reports no change and the files are byte-identical.
- **SC-004** A sibling's `configure` exiting non-zero stops `configure` with exit `2` and the sibling's
  output visible; nothing after it in the order runs.
- **SC-005** `specify bundle validate` on `bundle/` passes offline (warnings allowed) and
  `tools/build.py --check` passes on every commit of `main`.
- **SC-006** The launchers run on Windows (PowerShell), macOS and Linux in CI; `configure --dry-run` on
  the fixture project prints the same report on all three.
