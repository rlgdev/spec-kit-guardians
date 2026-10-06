# Getting started with the Guardians

This is the one page to read before anything else. It takes a Spec Kit project from nothing to a working
scopeGuard + archiGuard + auditGuard setup, tells you what every step must print, and what to do when it does
not. No prior knowledge of the three tools is needed; their READMEs are the reference once things run.

**What you get.** Three deterministic checkers that run inside the normal Spec Kit commands:

| Guardian | Keeps | You notice it when |
|----------|-------|--------------------|
| **scopeGuard** | no user story or requirement of `spec.md` is dropped by the plan, the tasks or the implementation | `/speckit.plan` or `/speckit.tasks` stops with `[FAIL] US3 ... missing from plan.md` and the agent puts it back |
| **archiGuard** | the plan and the code obey the architecture: domain map, rulebook, fitness functions, design sign-off, handover to testing | `/speckit.plan` stops with `[A3.3] ARCH-201 ... is missing`, or an agent edit of a signed plan is blocked |
| **auditGuard** | a tamper-evident record of every command, gate verdict, waiver, human decision and out-of-band change, verifiable against git | a folder `audit/` grows with your work; `auditguard verify` proves nothing was edited afterwards |

**Guardians** is the bundle that installs the three at versions tested together, plus two commands:
`guardians configure` (configures the three in the right order) and `guardians verify` (tells you where their
configurations disagree).

---

## 0. Before you start: the checklist

Run each line. If one fails, fix it before going on; nothing below works without it.

| Need | Check | If it fails |
|------|-------|-------------|
| Python 3.9 or newer | `python3 --version` (Windows: `python --version`) | install Python from python.org or your package manager. On Windows, do **not** rely on the Microsoft Store `python3` alias: the launchers skip it |
| git 2.20 or newer | `git --version` | install git |
| Spec Kit 1.0.1 or newer | `specify version` | `uv tool install specify-cli` (or `pip install specify-cli`); upgrade with `uv tool upgrade specify-cli` |
| a Spec Kit project | `ls .specify/` prints `extensions` ... | `specify init <name> --integration claude` (or your agent), then `cd` into it |
| the project is a git repository, at its root | `git rev-parse --show-toplevel` prints the project directory | `git init -b main`; auditGuard's git checks need the project root to be the repository root |
| an agent integration | `.claude/` (Claude Code), `.github/` (Copilot), ... exists in the project | pick one at `specify init`; the gates themselves run without an agent, from the shell |

Everything below is run **from the project root** (the directory that contains `.specify/`). Windows users:
use the `.ps1` launcher where a `.sh` one is shown, for example
`.specify/extensions/guardians/scripts/powershell/guardians.ps1 configure`.

---

## 1. Install

### Path A: the bundle (one command, pinned versions)

```bash
specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/extensions.json --name guardians --install-allowed
specify preset catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/presets.json    --name guardians --install-allowed
specify bundle catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/bundles.json
specify bundle install guardians
```

Spec Kit asks you to confirm installs from a URL: answer `y`. **Expected:** `specify extension list` shows
`scopeguard`, `archiguard`, `auditguard` and `guardians`; `specify preset list` shows `archiguard-templates`.

> **Not available yet?** The bundle resolves its components through GitHub release assets. Until **auditGuard
> `v0.1.0`** and **Guardians `v0.1.0`** are published (scopeGuard `v0.4.0` and archiGuard `v0.1.0` are), `bundle
> install` fails downloading them. Use path B meanwhile; the result is identical.

### Path B: one extension at a time

From the release assets:

```bash
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.4.0/scopeguard.zip
specify extension add archiguard --from https://github.com/rlgdev/spec-kit-archiguard/releases/download/v0.1.0/archiguard.zip
specify preset add --from https://github.com/rlgdev/spec-kit-archiguard/releases/download/v0.1.0/archiguard-preset.zip
specify extension add auditguard --from https://github.com/rlgdev/spec-kit-auditguard/releases/download/v0.1.0/auditguard.zip
specify extension add guardians  --from https://github.com/rlgdev/spec-kit-guardians/releases/download/v0.1.0/guardians.zip
```

Or, for a release that does not exist yet, from checkouts of the repositories (`--dev` installs the checkout as
it is; the same works with the `dist/<id>.zip` that `python tools/build.py` builds in each checkout):

```bash
for id in scopeguard archiguard auditguard guardians; do
  git clone --depth 1 https://github.com/rlgdev/spec-kit-$id ../spec-kit-$id
  specify extension add --dev ../spec-kit-$id
done
specify preset add --dev ../spec-kit-archiguard/preset
```

**Do not install the `scopeguard-templates` preset.** archiGuard wraps `/speckit.plan` and `/speckit.tasks` and
runs the scope gate itself; a second wrap runs it twice. (`guardians verify` tells you if it is there.)

### Behind a corporate proxy or with an internal catalog

Mirror the release archives (`<id>.zip`, `archiguard-preset.zip`, `guardians-bundle.zip`) into your internal
catalog and pin them by version **and** sha256: every release attaches `SHA256SUMS`, and the archives are built
reproducibly, so the hash of a mirrored file equals the published one. Point the three `catalog add` commands at
your mirror of `catalog/*.json` with the `download_url` values rewritten.

---

## 2. Configure the three together

```bash
bash .specify/extensions/guardians/scripts/bash/guardians.sh configure
# inside your agent instead: /speckit.guardians.configure   (Claude Code in Spec Kit 1.x: /speckit-guardians-configure)
```

What it does, in this order: sets scopeGuard to `integration: embedded` (archiGuard runs the scope gate), adds
the audit trail to archiGuard's edit guard, runs the three tools' own `configure` commands, orders the hooks so
auditGuard records first and last, and prints the alignment report. **Expected ending:**

```text
  RESULT: OK | 11 ok, 0 warnings, 0 failures
```

with `[OK]` on every check and `[--] codeowners` (no CODEOWNERS file yet; see step 3). Run it a second time:
it prints `No change needed.` The three files it changed (`scopeguard-config.yml`,
`archiguard-config.yml`, `.specify/extensions.yml`) are plain line edits: read them in `git diff`.

If the result is not `OK`:

| Line | Meaning | Do |
|------|---------|----|
| `[FAIL] installed : not installed: ...` | an extension is missing | install it (step 1), run `configure` again |
| `[FAIL] git_base_agrees : archiguard git.base=main, auditguard golden.git.base=develop` | the two tools name different base branches; Guardians never picks a side | edit one of the two files named in the `fix:` line, run `configure` again |
| `[FAIL] preset_matches_integration : archiGuard is configured inline but archiguard-templates is not installed` | the preset is missing, so the gates fell back to hooks | `specify preset add ...` (step 1), run `configure` again |
| `[WARN] gitattributes : .gitattributes lacks ...` | auditGuard's hash chain needs its files excluded from line-ending conversion | `bash .specify/extensions/auditguard/scripts/bash/auditguard.sh configure` writes the lines |
| `Guardians: ERROR: ... configure failed (exit 2)` | one tool's own `configure` refused (usually a typo in its config file: unknown keys are errors) | read its output above the error, fix the key it names |

Then commit:

```bash
git add .specify .gitattributes && git commit -m "Guardians: install and configure"
```

`.specify/` holds the installed extensions, their configs, the standards lock and the ledger: it is part of the
project, and CI reads it.

---

## 3. Once per project

Three things no tool can decide for you. `guardians configure` and the tools' own `configure` print what is
still missing.

### 3.1 Bind archiGuard to your architecture standards

archiGuard checks the plan and the code against a **rulebook** (architecture rules as data, with the skill text
the agent reads), a **profile** (the rule set for your stack) and the **domain map** (contexts, what they own,
how they may talk to each other). They live under `.specify/standards/`, usually as a git submodule of a
standards repository pinned by tag.

```bash
A=.specify/extensions/archiguard/scripts/bash/archiguard.sh
bash $A scaffold rulebook       # no standards yet? starting files under .specify/standards/
bash $A scaffold domain-map
```

Then in `.specify/extensions/archiguard/archiguard-config.yml` set:

```yaml
standards:
  rulebook: acme-standards@v2026.10.1    # <name>@<tag> of the standards repository
  profile: java-service                  # the central rule set for this stack
domain:
  pin: "1.4.0"                           # the domain map version this repository follows
```

and resolve the lock (commit it; CI re-resolves and fails on drift):

```bash
bash $A validate-standards
bash $A resolve                 # -> .specify/archiguard/standards.lock.yml
git add .specify && git commit -m "archiGuard: bind to acme-standards@v2026.10.1"
```

Until the lock exists, `/speckit.plan` stops at step A with `cannot evaluate` (exit `2`): that is the
fail-closed design, not a bug. [archiGuard's README](https://github.com/rlgdev/spec-kit-archiguard#bind-the-project-to-its-standards)
and [docs/standards.md](https://github.com/rlgdev/spec-kit-archiguard/blob/main/docs/standards.md) describe the
rulebook format.

### 3.2 Open auditGuard's first sprint

A **person** opens and closes sprints; the agent is blocked from it.

```bash
bash .specify/extensions/auditguard/scripts/bash/auditguard.sh sprint open S-2026-41 \
     --name "Sprint 41" --start 2026-10-06 --end 2026-10-17 --by "Your Name"
git add audit && git commit -m "auditGuard: open sprint S-2026-41"
```

Events recorded while no sprint is open land in `audit/sprints/_unassigned/` and `auditguard check` reports
them, so do this before the first `/speckit.specify`.

### 3.3 Protect what the tools rely on

Add a `CODEOWNERS` file (`.github/CODEOWNERS`) so that a change of the standards, the lock, the ledger, the audit
trail or an installed extension needs the lead architect's review. `guardians verify` checks it covers:

```text
audit/                      @your-org/lead-architects
.specify/standards/         @your-org/lead-architects
.specify/archiguard/        @your-org/lead-architects
.specify/extensions/        @your-org/lead-architects
```

Commit it with the project. The tools' own guards (archiGuard's edit guard, auditGuard's `pre_tool_use` guard)
stop the **agent**; CODEOWNERS and CI stop everyone else.

---

## 4. Day to day

Use Spec Kit as before. What changes:

- `/speckit.plan`, `/speckit.tasks`, `/speckit.implement` now contain two mandatory steps: **A** (right after
  Setup: the domain guard, the applicable rules, the scope contract) and **B** (before the completion report:
  the gates, with a bounded repair loop). The agent repairs what the gates find; when it cannot within the
  budget (default 3 iterations), it stops and writes an escalation note (`specs/<feature>/gates/escalation-*.md`,
  `scopeguard-escalation-*.md`) with the decision it needs from you.
- `/speckit.analyze` saves its report for the A3.6 check; `/speckit.implement` starts only on a **signed design**.
- Every command is recorded in `audit/` with the hashes of what it touched. Commit `audit/` with your work.

The commands reserved for **people** (the agent is blocked from them, and that is the point):

```bash
A=.specify/extensions/archiguard/scripts/bash/archiguard.sh
U=.specify/extensions/auditguard/scripts/bash/auditguard.sh

bash $A signoff --by "Lead architect"            # the design authority signs the plan (after plan, tasks and analyze are green)
bash $A reopen  --by "Lead architect" --reason "..."   # a design change after the sign-off
bash $A ledger add --id ADR-0042 --type adr --title "..." --owner "..." --status approved --approver "..."
bash $U decide escalation:<note> accept --by "Your Name" --reason "..."   # answer an escalation
bash $U check                                     # the completeness rules of the open sprint
bash $U sprint close S-2026-41 --by "Your Name"   # seal the sprint, then: anchor --push, export
```

A five-minute smoke test on a fresh project, without an agent:

```bash
bash .specify/scripts/bash/create-new-feature.sh --json --short-name demo "Demo feature"   # a feature branch and specs/001-demo/
#   write specs/001-demo/spec.md with one "### User Story 1 - ..." and one "- **FR-001**: ..."
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh inventory         # the scope contract
bash .specify/extensions/archiguard/scripts/bash/archiguard.sh run plan a        # step A: PASS, or what is missing (lock, map)
bash .specify/extensions/auditguard/scripts/bash/auditguard.sh show --all        # the events recorded so far
bash .specify/extensions/guardians/scripts/bash/guardians.sh verify              # RESULT: OK
```

---

## 5. CI: one required check

```yaml
# .github/workflows/guardians.yml
name: guardians
on: [pull_request]
jobs:
  guardians:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0            # auditGuard's golden checks and archiGuard's traceability read the history
          submodules: true          # the standards repository at its pinned tag
      - run: git fetch -q origin "refs/notes/*:refs/notes/*" "refs/tags/*:refs/tags/*" || true
      - uses: rlgdev/spec-kit-guardians@v0.1.0
        with:
          features: all             # or specs/001-my-feature
```

It runs scopeGuard's check, archiGuard's CI check (every gate once on the final commit, lock drift, the ledger),
auditGuard's verify (chains, seals, evidence, the golden sources) and `guardians verify`, and writes the result
to the job summary. Each part can be switched off with `scopeguard: "false"` and so on. Make the job a required
check on the protected branch.

Until Guardians `v0.1.0` is released, use the three siblings' actions directly (`rlgdev/spec-kit-scopeguard@v0.4.0`,
`rlgdev/spec-kit-archiguard@v0.1.0`, `rlgdev/spec-kit-auditguard@v0.1.0`) and add one step:

```yaml
      - run: python .specify/extensions/guardians/scripts/python/guardians.py verify
```

On other CI systems every tool is one Python command on the installed extension, for example
`python .specify/extensions/archiguard/scripts/python/archiguard.py ci --junit reports/archiguard.xml`; the
READMEs have Bitbucket Pipelines examples.

---

## 6. What was written where

| File | Written by | Commit it? |
|------|-----------|------------|
| `.specify/extensions/<id>/` | the install: engine, commands, launchers, `<id>-config.yml` | yes |
| `.specify/extensions.yml` | Spec Kit (hook registry); `configure` sets `enabled` and `priority` | yes |
| `.specify/presets/archiguard-templates/` | the preset install | yes |
| `.claude/skills/speckit-*/` (or your agent's folder) | Spec Kit renders the wrapped commands | yes |
| `.claude/settings.json` | Spec Kit wires the agent events (edit guard, audit guard, sessions) | yes |
| `.specify/standards/`, `.specify/archiguard/standards.lock.yml`, `.specify/archiguard/ledger.jsonl` | you (step 3.1), `archiguard resolve`, `archiguard ledger add` | yes |
| `specs/<feature>/gates/` | the gates: verdict files, sign-off, escalation notes | yes (evidence) |
| `specs/<feature>/.scopeguard/`, `scopeguard-escalation-*.md` | scopeGuard's iteration history and escalations | the history is transient; the escalation note until decided |
| `audit/` | auditGuard; **never** by hand or by the agent | yes, always |
| `.gitattributes` | `auditguard configure` adds three lines | yes |
| `.specify/extensions/<id>/local-config.yml` | you, for workstation-only overrides | no (CI ignores it) |

The config files, with their full reference: [scopeGuard](https://github.com/rlgdev/spec-kit-scopeguard/blob/main/config-template.yml)
(`scopeguard-config.yml`), [archiGuard](https://github.com/rlgdev/spec-kit-archiguard/blob/main/docs/configuration.md)
(`archiguard-config.yml`, `scope-config.yml`), [auditGuard](https://github.com/rlgdev/spec-kit-auditguard/blob/main/docs/configuration.md)
(`auditguard-config.yml`), [Guardians](../config-template.yml) (`guardians-config.yml`, optional). In every one
of them **an unknown key is an error**: a typo never switches a gate off silently.

Environment variables for one run: `SCOPEGUARD_PYTHON` / `ARCHIGUARD_PYTHON` / `AUDITGUARD_PYTHON` /
`GUARDIANS_PYTHON` (the interpreter to use), `SCOPEGUARD_MODE=report`, `ARCHIGUARD_INTEGRATION`,
`ARCHIGUARD_MAX_ITERATIONS`, `AUDITGUARD_ACTOR`. CI (`CI=true`) ignores the overrides.

---

## 7. When something is off

| Symptom | Cause | Fix |
|---------|-------|-----|
| `scopeGuard: ERROR: no Python 3.8+ interpreter found` (any tool) | nothing usable on PATH | install Python, or set `<ID>_PYTHON=/path/to/python`; with `uv` installed the launchers also use specify-cli's Python |
| the gate runs twice in `/speckit.plan` | both the inline step and a hook are on, or both presets are installed | `guardians verify` names it; `specify preset remove scopeguard-templates`, then `guardians configure` |
| `/speckit.plan` says `skipped` for the gates | the wrapped step is off because the config says `hooks`, or the other way round | `guardians configure` (it runs every tool's configure); `[WARN] hooks_match_integration` names the tool |
| `cannot evaluate` (exit 2) in archiGuard step A | no standards lock, no domain map pin, or a pin that moved | step 3.1; the message names the file |
| `A4.1 ... no design sign-off` on `/speckit.implement` | implement starts only on a signed design | `archiguard signoff --by ...` after plan, tasks and analyze are green |
| `auditguard check` reports `_unassigned` events | no sprint was open | open a sprint (3.2); the events stay where they are, as a record |
| `auditguard verify` fails `G3 unexplained_commit` | a commit touched a design artefact or code outside any recorded command (a hand edit, hooks skipped) | that is the finding; the audit trail now shows the author. Decide it with `auditguard decide` or `note` |
| `guardians verify` exits `2` with `cannot read YAML` | no PyYAML and no sibling installed | `python -m pip install pyyaml`, or run with specify-cli's Python (`GUARDIANS_PYTHON`) |
| a reinstall turned hooks back on | a sibling's reinstall registers its manifest hooks and priorities | `guardians configure` re-applies everything; it is idempotent |

---

## 8. Upgrading and uninstalling

A bundle version is a tested combination of the three. To move a project to the next one:

```bash
specify bundle update guardians                                  # or: specify bundle install <new bundle.yml> --refresh
bash .specify/extensions/guardians/scripts/bash/guardians.sh configure
```

`verify` reports a sibling whose version its neighbours do not accept (`versions_in_range`). Your config files
are kept across upgrades.

```bash
specify bundle remove guardians       # removes what the bundle installed; audit/ and your configs stay
```

---

## 9. Where to go next

- the family at a glance and what `configure` / `verify` do: [README.md](../README.md)
- the gates in detail: [scopeGuard](https://github.com/rlgdev/spec-kit-scopeguard#readme),
  [archiGuard](https://github.com/rlgdev/spec-kit-archiguard#readme), [auditGuard](https://github.com/rlgdev/spec-kit-auditguard#readme)
- worked examples: [`scopeguard/examples`](https://github.com/rlgdev/spec-kit-scopeguard/tree/main/examples) (a dropped story, an
  escalation), [`archiguard/examples/orders`](https://github.com/rlgdev/spec-kit-archiguard/tree/main/examples) (planted
  violations), [`auditguard/examples/orders`](https://github.com/rlgdev/spec-kit-auditguard/tree/main/examples) (two sprints with the
  viewer)
- contributing and releasing: [CONTRIBUTING.md](../CONTRIBUTING.md)
