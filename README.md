# Guardians for Spec Kit

[![CI](https://github.com/rlgdev/spec-kit-guardians/actions/workflows/ci.yml/badge.svg)](https://github.com/rlgdev/spec-kit-guardians/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **New here?** Read [docs/getting-started.md](docs/getting-started.md): prerequisites, the install, the first
> `configure`, what to do once per project, CI, and what every message means. Ten minutes, no prior knowledge of the
> three tools needed.

One cover for the three Guardians of the AI-native SDLC on [GitHub Spec Kit](https://github.com/github/spec-kit):

| Guardian | Keeps | Repository |
|----------|-------|------------|
| **scopeGuard** | no user story or requirement of `spec.md` is dropped by plan, tasks or implementation | [spec-kit-scopeguard](https://github.com/rlgdev/spec-kit-scopeguard) |
| **archiGuard** | the design and the code conform to the architecture: domain guard, plan conformance, fitness functions, handover 4→5, the edit guard | [spec-kit-archiguard](https://github.com/rlgdev/spec-kit-archiguard) |
| **auditGuard** | a tamper-evident trail of every command, gate report, waiver, human decision and out-of-band change, verifiable against git | [spec-kit-auditguard](https://github.com/rlgdev/spec-kit-auditguard) |

Guardians adds no fourth gate. It is a **Spec Kit bundle** that installs the three (and archiGuard's preset) at
versions tested together, plus a thin extension with two commands:

- `guardians configure` — runs the three tools' own `configure` in order and does the cross-wiring each of them
  documents but cannot do for the others: scopeGuard `integration: embedded` (archiGuard runs the scope gate),
  the audit trail in archiGuard's edit guard, auditGuard's hooks first and last on the events they share.
- `guardians verify` — twelve checks that the three configurations agree (versions, integration, hook order,
  base branch, edit guard, modes, `.gitattributes`, CODEOWNERS). Exit `1` on a failure; for CI.

Everything else stays where it is: each Guardian keeps its own engine, config file, release cadence and
documentation. Guardians writes three things and nothing else: hook priorities in `.specify/extensions.yml`,
scopeGuard's `integration`, archiGuard's `edit_guard.always_readonly`. Values one tool owns alone (git base,
mode, budgets) are compared, never written.

## Install

Requires Spec Kit (`specify-cli`) 1.0.3 or newer and Python 3.9+. From your Spec Kit project root:

```bash
# 1. the family's catalogs (extensions, the preset, the bundle)
specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/extensions.json --name guardians --install-allowed
specify preset catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/presets.json    --name guardians --install-allowed
specify bundle catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/bundles.json

# 2. scopeGuard, archiGuard, auditGuard, Guardians and archiguard-templates at the pinned versions
specify bundle install guardians

# 3. configure the three together (a bundle installs; it runs nothing afterwards)
bash .specify/extensions/guardians/scripts/bash/guardians.sh configure
#    Windows: .specify/extensions/guardians/scripts/powershell/guardians.ps1 configure
#    or, inside your agent: /speckit.guardians.configure
```

Then bind archiGuard to its standards and open auditGuard's first sprint as their READMEs describe; `configure`
prints what is still missing. `specify bundle info guardians` shows the exact component set before installing.

<details>
<summary>Without the bundle (one extension at a time)</summary>

```bash
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.4.1/scopeguard.zip
specify extension add archiguard --from https://github.com/rlgdev/spec-kit-archiguard/releases/download/v0.1.1/archiguard.zip
specify preset add --from https://github.com/rlgdev/spec-kit-archiguard/releases/download/v0.1.1/archiguard-preset.zip
specify extension add auditguard --from https://github.com/rlgdev/spec-kit-auditguard/releases/download/v0.2.0/auditguard.zip
specify extension add guardians  --from https://github.com/rlgdev/spec-kit-guardians/releases/download/v0.1.3/guardians.zip
bash .specify/extensions/guardians/scripts/bash/guardians.sh configure
```

Do not add the `scopeguard-templates` preset: archiGuard wraps the commands and runs the scope gate itself.

</details>

Two notes on Spec Kit's catalogs: a project-scoped extension catalog replaces the built-in catalogs for that
project (first-party extensions still install from the package; `specify extension catalog list` shows the
stack); and an extension already installed outside the bundle must be at the pinned version, or `bundle install`
stops before changing anything.

## What `configure` does

```text
Guardians 0.1.3 | configure | /work/orders
config: .specify/extensions/guardians/guardians-config.yml | order: scopeguard, archiguard, auditguard

  Siblings:
  scopeGuard : scopeGuard 0.4.1 | configure
  archiGuard : archiGuard 0.1.1 | configure
  auditGuard : auditGuard 0.2.0 | configure

  Changed:
    .specify/extensions/scopeguard/scopeguard-config.yml: integration: inline -> embedded (archiGuard runs the scope gate)
    .specify/extensions/archiguard/archiguard-config.yml: edit_guard.always_readonly += audit/**, .specify/extensions/auditguard/**
    .specify/extensions.yml: 20 hook priorities set: auditguard after_* 10 -> 90 (10), auditguard before_* 10 -> 1 (10)

  Tools:
    scopeGuard : 0.4.1 | integration embedded | mode enforce | hooks 0/5
    archiGuard : 0.1.1 | integration inline | mode enforce | hooks 0/6 | scope gate in pipeline | preset installed
    auditGuard : 0.2.0 | integration hooks | mode record | hooks 20/20
    Guardians  : 0.1.3

  Checks:
    [OK]   installed                   scopeguard, archiguard, auditguard, guardians
    [OK]   preset_matches_integration  archiguard-templates installed, archiGuard integration inline; scopeguard-templates absent
    [OK]   versions_in_range           scopeGuard 0.4.1 in archiGuard's >=0.3.0,<0.5; scopeGuard 0.4.1 in auditGuard's >=0.4,<0.6; ...
    [OK]   scopeguard_embedded         scopeGuard integration embedded (archiGuard runs the scope gate)
    [OK]   auditguard_integration      auditGuard integration hooks
    [OK]   hook_order                  no event is shared by two Guardians (gates inline / embedded); auditGuard records alone
    [OK]   hooks_match_integration     scopeGuard 0/5 (embedded); archiGuard 0/6 (inline); auditGuard 20/20 (hooks)
    [OK]   git_base_agrees             both use base branch main
    [OK]   edit_guard_covers_audit     archiGuard's edit guard covers audit/**, .specify/extensions/auditguard/**
    [OK]   modes_agree                 scopeGuard and archiGuard enforce; auditGuard record (records, not compared)
    [OK]   gitattributes               the audit trail is excluded from line-ending conversion
    [--]   codeowners                  no CODEOWNERS file; consider owners for audit/, .specify/standards/, ...

  RESULT: OK | 11 ok, 0 warnings, 0 failures
```

Order of work: the two config edits first (so scopeGuard's own `configure` already sees `embedded` and switches
its hooks off), then the three `configure` commands in the configured order, then the hook priorities, then the
report. `--dry-run` lists every edit under `Would change:` instead of making it and passes `--dry-run` to the siblings. A second run
changes nothing.

Why the hook order: on an event two Guardians share, auditGuard must record the start before a gate runs and the
end after the gate's verdict - otherwise `command.finished` misses that verdict until the next hook. Spec Kit runs
hooks by `priority` (lower first, default 10); Guardians gives auditGuard's `before_*` hooks 1 and `after_*` 90.
With the default stack (archiGuard inline, scopeGuard embedded) no event is shared and the order is moot; it
matters as soon as archiGuard runs through hooks.

## What `verify` checks

| Check | Default | Fails when |
|-------|---------|-----------|
| `installed` | fail | one of the four extensions is missing |
| `preset_matches_integration` | fail | archiGuard says `inline` without `archiguard-templates` (it silently falls back to hooks); the preset is installed while archiGuard runs through hooks (gates twice); `scopeguard-templates` is installed |
| `versions_in_range` | fail | scopeGuard's version is outside archiGuard's `gates.scope.version`, or a sibling's version is outside auditGuard's `collectors.<id>.version` |
| `scopeguard_embedded` | fail | archiGuard runs the scope gate but scopeGuard is not `embedded` |
| `auditguard_integration` | warn | auditGuard's integration is neither `hooks` nor `workflow` |
| `hook_order` | fail | on a shared event an enabled auditGuard `before_*` hook does not run first or an `after_*` hook does not run last |
| `hooks_match_integration` | warn | a tool has hooks enabled although its integration is not `hooks`, or none enabled although it is |
| `git_base_agrees` | fail | archiGuard `git.base` ≠ auditGuard `golden.git.base` - two files, a person decides |
| `edit_guard_covers_audit` | fail | archiGuard's edit guard is off or does not list auditGuard's read-only paths |
| `modes_agree` | warn | scopeGuard `mode` ≠ archiGuard `mode` (auditGuard's `record`/`enforce` means something else and is only shown) |
| `gitattributes` | warn | auditGuard's three `-text` lines are missing |
| `codeowners` | warn | a CODEOWNERS file exists but names no owner for `audit/`, `.specify/standards/`, `.specify/archiguard/` or `.specify/extensions/` |

Each `[WARN]` and `[FAIL]` line comes with a `fix:` - a command, or the two files and keys that disagree.
Severities are set in `guardians-config.yml` (below). `verify --json` prints the same as data; exit `1` on a
`FAIL`.

The checks read the siblings through their own interfaces: `integration`, `effective_integration`, `mode` and
`scope_in_pipeline` come from each tool's `configure --dry-run --json` when it prints them (so workstation
overrides and fallbacks count; auditGuard prints no `effective_integration`, archiGuard no `mode`), the rest
from their committed config files and `.specify/extensions.yml`. YAML is read with PyYAML when
present, else with the reader of the installed auditGuard or archiGuard.

## Commands

| Command | What it does |
|---------|--------------|
| `/speckit.guardians.configure` | `configure`: cross-wire, run the three configures, order the hooks, report |
| `/speckit.guardians.verify` | `verify`: the alignment report, nothing written |

With skills-based integrations (such as Claude Code in Spec Kit 1.x) these appear as `/speckit-guardians-configure`
and `/speckit-guardians-verify`. The same engine runs without an agent:

```bash
G=.specify/extensions/guardians/scripts/bash/guardians.sh      # Windows: scripts/powershell/guardians.ps1
bash $G configure [--dry-run] [--no-siblings] [--verbose] [--json]
bash $G verify [--json]
bash $G version
```

Exit codes: `0` ok · `1` `verify` found a failure (`configure`: one remains after it ran) · `2` cannot run (no
project, config error, a sibling's `configure` failed - its output is shown and nothing after it runs).

## Configuration

Optional: `.specify/extensions/guardians/guardians-config.yml` (created from `config-template.yml` on install;
the template documents the defaults).

```yaml
version: 1
order: [scopeguard, archiguard, auditguard]   # the siblings' configure commands run in this order
hook_priority:
  auditguard: { before: 1, after: 90 }        # auditGuard records first and last on a shared event
  default: 10                                 # gates keep Spec Kit's default (set only when missing)
checks:                                       # fail | warn | off  (quote "off" or write it as a string: YAML reads a bare off as false)
  git_base_agrees: fail
  codeowners: warn
```

## CI

One action for the family - the three siblings' own checks (pinned to the bundle's versions) and the alignment
check, each switchable:

```yaml
- uses: actions/checkout@v5
  with: { fetch-depth: 0 }          # auditGuard's golden checks need the history, notes and tags
- uses: rlgdev/spec-kit-guardians@v0.1.3
  with:
    features: all                   # or specs/001-my-feature
    auditguard-golden: "true"
    # scopeguard: "false"  archiguard: "false"  auditguard: "false"  verify: "false"  to skip a part
```

The verify output goes to the job summary. archiGuard's and auditGuard's actions use the engine the project installed
(`.specify/extensions/<id>/`), falling back to their own; scopeGuard's action at the pinned `v0.4.1` runs its own engine
(it still reads the project's `scopeguard-config.yml`). GitHub resolves every action a composite action uses
before it runs, so this action needs the three siblings released at the bundle's pins (`rlgdev/spec-kit-<id>@v<pin>`);
until then use the siblings' actions directly and run `guardians verify` as a plain step.

## Upgrading the family

A bundle version is a tested combination. To move a project: `specify bundle update guardians` (or
`specify bundle install <new bundle.yml> --refresh`), then `guardians configure`. `verify` reports a sibling whose
version its neighbours do not accept (`versions_in_range`). To release a new combination of this bundle: bump the
pins in `bundle/bundle.yml`, the catalogs and `action.yml` (`tools/build.py --check` keeps them equal), run the
e2e against the new tags, release.

## Uninstall

```bash
specify bundle remove guardians       # removes what the bundle installed and nothing another bundle needs
```

Guardians' three edits stay in place (they are the siblings' documented settings); revert them with
`git checkout` of the two config files and `.specify/extensions.yml` if you remove the siblings too.

## Development

```bash
python -m pytest -q                   # tests on the siblings' real config templates (AUDITGUARD_SRC enables the YAML-fallback test; all three *_SRC the check-family test)
python tools/build.py --check         # versions, pins and catalogs agree; referenced files exist
python tools/check-family.py          # the four repositories agree (pins, catalogs, CI refs, ranges, launchers; siblings as ../spec-kit-<id> or *_SRC)
python tools/build.py                 # dist/guardians.zip, dist/guardians-bundle.zip, dist/SHA256SUMS
tools/e2e-speckit.sh                  # against a real Spec Kit install: specify init, the siblings from checkouts, configure, verify
```

To release, bump the version in `extension.yml`, `scripts/python/guardians_core/__init__.py`, `bundle/bundle.yml`
(bundle version and the `guardians` pin), the three catalogs and the sibling pins in `action.yml`, add the
CHANGELOG entry and push a `vX.Y.Z` tag; the release workflow attaches `guardians.zip`, `guardians-bundle.zip` and
`SHA256SUMS`. The specification is in [docs/specification.md](docs/specification.md); [CONTRIBUTING.md](CONTRIBUTING.md) has the
conventions and the release order of the family.

## License

MIT - see [LICENSE](LICENSE).
