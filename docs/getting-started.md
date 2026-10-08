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
| Spec Kit 1.0.3 or newer | `specify version` | `uv tool install specify-cli` (or `pip install specify-cli`); upgrade with `uv tool upgrade specify-cli` |
| a Spec Kit project | `ls .specify/` prints `memory`, `scripts` and `templates` (`extensions/` only appears after the first install in step 1) | `specify init <name> --integration claude` (or your agent), then `cd` into it |
| the project is a git repository, at its root | `git rev-parse --show-toplevel` prints the project directory | `git init -b main`; auditGuard's git checks need the project root to be the repository root |
| an agent integration | `.claude/` (Claude Code), `.github/` (Copilot), ... exists in the project | pick one at `specify init`; the gates themselves run without an agent, from the shell |

Everything below is run **from the project root** (the directory that contains `.specify/`). Windows users:
use the `.ps1` launcher where a `.sh` one is shown, for example
`.specify/extensions/guardians/scripts/powershell/guardians.ps1 configure`.

---

## 1. Install

### Path A: the bundle (one command, pinned versions)

Copy all eight lines. The first two of each group matter: a project catalog file (`.specify/extension-catalogs.yml`,
`.specify/preset-catalogs.yml`) **replaces** Spec Kit's own catalogs instead of adding to them, so without Spec
Kit's `default` and `community` lines every other extension of the project (git, agent-context, ...) disappears
from `specify extension search`, `info` and `update`.

```bash
specify extension catalog add https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.json           --name default   --priority 1  --install-allowed
specify extension catalog add https://raw.githubusercontent.com/github/spec-kit/main/extensions/catalog.community.json --name community --priority 20 --no-install-allowed
specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/extensions.json --name guardians --priority 10 --install-allowed
specify preset catalog add    https://raw.githubusercontent.com/github/spec-kit/main/presets/catalog.json              --name default   --priority 1  --install-allowed
specify preset catalog add    https://raw.githubusercontent.com/github/spec-kit/main/presets/catalog.community.json    --name community --priority 20 --no-install-allowed
specify preset catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/presets.json    --name guardians --priority 10 --install-allowed
specify bundle catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/bundles.json    --id guardians
specify bundle install guardians
```

**Expected:** `specify extension list` shows `scopeguard`, `archiguard`, `auditguard` and `guardians` next to
every extension the project had before; `specify preset list` shows `archiguard-templates`;
`specify extension catalog list` shows `default`, `guardians` and `community`.

- `community` gets priority 20, after the Guardians catalog (10): it is discovery-only, and the trusted catalog
  must win if a Guardians id ever appears there.
- Do you keep catalogs in `~/.specify/extension-catalogs.yml` (or `preset-catalogs.yml`)? The project file replaces
  those too: add their entries here instead of the two Spec Kit lines.
- Forgot the Spec Kit lines, or installed with older instructions? Nothing is uninstalled, the other extensions
  are only hidden: `guardians configure` (step 2) adds the two catalogs back.

> **Download fails?** The bundle resolves its components through the GitHub release assets of the pinned versions
> (scopeGuard `v0.4.1`, archiGuard `v0.1.1`, auditGuard `v0.1.0`, Guardians `v0.1.2`). Where GitHub is not
> reachable, use path B's checkout variant (`--dev`); the result is identical.

### Path B: one extension at a time

From the release assets:

```bash
specify extension add scopeguard --from https://github.com/rlgdev/spec-kit-scopeguard/releases/download/v0.4.1/scopeguard.zip
specify extension add archiguard --from https://github.com/rlgdev/spec-kit-archiguard/releases/download/v0.1.1/archiguard.zip
specify preset add --from https://github.com/rlgdev/spec-kit-archiguard/releases/download/v0.1.1/archiguard-preset.zip
specify extension add auditguard --from https://github.com/rlgdev/spec-kit-auditguard/releases/download/v0.1.0/auditguard.zip
specify extension add guardians  --from https://github.com/rlgdev/spec-kit-guardians/releases/download/v0.1.2/guardians.zip
```

Spec Kit asks you to confirm each `specify extension add --from` install (`Continue with installation? [y/N]`): answer `y`.
The preset install does not ask.

Or, for a release that does not exist yet, from checkouts of the repositories (`--dev` installs the checkout as
it is; `--from` takes only an https or loopback-http URL, not a local `dist/<id>.zip`):

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
reproducibly, so the hash of a mirrored file equals the published one. Point the family's three `catalog add` commands at
your mirror of `catalog/*.json` with the `download_url` values rewritten, and keep the catalogs your projects use
otherwise (Spec Kit's, or your mirror of them) in the same files: `guardians verify` warns (`catalogs_keep_defaults`)
when a catalog file hides them. If your policy replaces Spec Kit's catalogs on purpose, switch that check off in
`guardians-config.yml`.

---

## 2. Configure the three together

```bash
bash .specify/extensions/guardians/scripts/bash/guardians.sh configure
# inside your agent instead: /speckit.guardians.configure   (Claude Code in Spec Kit 1.x: /speckit-guardians-configure)
```

What it does, in this order: sets scopeGuard to `integration: embedded` (archiGuard runs the scope gate), adds
the audit trail to archiGuard's edit guard, adds Spec Kit's catalogs back if a catalog file lists only the
Guardians', runs the three tools' own `configure` commands, has Spec Kit wire the agent events that
`specify bundle install` leaves out (archiGuard's edit guard, auditGuard's guard and session records: it runs
`specify extension disable guardians && specify extension enable guardians`), orders the hooks so auditGuard
records first and last, and prints the alignment report. **Expected ending:**

```text
  RESULT: OK | 13 ok, 0 warnings, 0 failures
```

with `[OK]` on every check and `[--] codeowners` (no CODEOWNERS file yet; see step 3). Run it a second time:
it prints `No change needed.` The three files it changed (`scopeguard-config.yml`,
`archiguard-config.yml`, `.specify/extensions.yml`) are plain line edits: read them in `git diff`. Spec Kit
wrote the agent events into your agent's settings (`.claude/settings.json` for Claude Code).

If the result is not `OK`:

| Line | Meaning | Do |
|------|---------|----|
| `[FAIL] installed                   not installed: ...` | an extension is missing | install it (step 1), run `configure` again |
| `[FAIL] git_base_agrees             archiguard git.base=main, auditguard golden.git.base=develop` | the two tools name different base branches; Guardians never picks a side | edit one of the two files named in the `fix:` line, run `configure` again |
| `[FAIL] preset_matches_integration  archiGuard is configured inline but archiguard-templates is not installed (it fell back to hooks)` | the preset is missing, so the gates fell back to hooks | `specify preset add ...` (step 1), run `configure` again |
| `[WARN] gitattributes               .gitattributes lacks 3 auditGuard line(s): ...` | auditGuard's hash chain needs its files excluded from line-ending conversion | `bash .specify/extensions/auditguard/scripts/bash/auditguard.sh configure` writes the lines |
| `NOTE: .specify/extensions/<tool>/<tool>-config.yml not found: copy ... to ..., then run guardians configure again` | the tool's config file is missing: deleted, or installed by a `bundle install` on Spec Kit 1.0.1 / 1.0.2, which do not create it (Guardians needs 1.0.3 for that reason) | make the copy the note names (the template is the tool's own default config), run `configure` again |
| `[WARN] catalogs_keep_defaults      .specify/extension-catalogs.yml replaces Spec Kit's extension catalogs and lacks default, community: ...` | the catalog file hides every other extension from search, info and update | when the file lists only the Guardians catalog, `configure` already added Spec Kit's two back; otherwise run the `fix:` commands (or add your `~/.specify/` catalogs to the file) |
| `[WARN] agent_events_wired          the agent events of archiGuard, auditGuard are not wired for claude (...)` or `NOTE: the agent events of ... are not wired (specify is not on PATH): run ...` | Spec Kit has not written the edit guard and the audit guard into your agent's settings (a bundle install does not) | `specify extension disable guardians && specify extension enable guardians`, then `configure` again |
| `ERROR: <tool> configure failed (exit N); nothing after it ran` (Guardians exits 2) | one tool's own `configure` refused with exit N (usually a bad value in its config file, or an unknown key: all three reject those) | the tool's own message is indented under the `<tool> : configure exited N` line just above; fix what it names, run `configure` again |

Then commit:

```bash
git add .specify .gitattributes audit
git add .claude        # Claude Code; otherwise your agent's folder (Spec Kit wired the agent events there)
git commit -m "Guardians: install and configure"
```

`.specify/` holds the installed extensions, their configs, the standards lock and the ledger, and `audit/` the trail
auditGuard's `configure` opened (`sprints.yml`): both are part of the project, and CI reads them.

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
bash $A scaffold rulebook --out .specify/standards   # no standards yet? starting files where standards.path points (run it first)
bash $A scaffold domain-map                          # -> .specify/standards/domain-map.yaml
```

Then in `.specify/extensions/archiguard/archiguard-config.yml` set the values of **your** standards repository.
`resolve` refuses a name or tag that differs from its `rulebook.yml`, and A0.1 fails when `pin` differs from the
map's `domain_map_version`. For the scaffolded starting files they are `example-standards@v0.1.0`, `java-service`
and `"1.0.0"`:

```yaml
standards:
  rulebook: acme-standards@v2026.10.1    # <name>@<tag>: the name and version in rulebook.yml of the standards repository
  profile: java-service                  # the central rule set for this stack (profiles/<name>.yml)
domain:
  pin: "1.4.0"                           # the domain_map_version of the domain map this repository follows
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
- `/speckit.plan` also needs the feature's handover record, `specs/<feature>/handover.yml` (written by the formal
  handover from the BA specification tool; `archiguard scaffold handover --feature-dir specs/<feature>` gives a
  starting file). Without it, step A stops with `cannot evaluate` (exit `2`), exactly like a missing lock.
- `/speckit.analyze` saves its report for the A3.6 check; `/speckit.implement` starts only on a **signed design**.
- Every command is recorded in `audit/` with the hashes of what it touched. Commit `audit/` with your work.
- A command a gate stops (an escalation, or `cannot evaluate`) ends there: its post-execution hooks do not run,
  also those of other extensions (git's commit, agent-context's update). The gate's output lists them under
  `NOT RUN` and the agent tells you; they run when the command is run again and passes. In a new project this is
  the first `/speckit.plan`: it stops at step A until the standards lock (3.1) and the feature's handover
  record exist.

The commands reserved for **people** (the agent is blocked from them, and that is the point):

```bash
A=.specify/extensions/archiguard/scripts/bash/archiguard.sh
U=.specify/extensions/auditguard/scripts/bash/auditguard.sh

bash $A signoff --by "Lead architect"            # the design authority signs the plan (after plan, tasks and analyze are green)
bash $A reopen  --by "Lead architect" --reason "..."   # a design change after the sign-off
bash $A ledger add --id ADR-0042 --type adr --title "..." --owner "..." --status approved --approver "..."
bash $U decide escalation:<note> accept --by "Your Name" --reason "..."   # answer an escalation
bash $U check                                     # the completeness rules of the open sprint
bash $U sprint close S-2026-41 --by "Your Name"   # seal the sprint; then commit audit/ and anchor it:
git add audit && git commit -m "Close sprint S-2026-41"
bash $U anchor --sprint S-2026-41 --push          # note on HEAD + annotated tag audit/S-2026-41, pushed
bash $U export --sprint S-2026-41                 # audit-pack-S-2026-41.zip, verifies offline with `verify --pack`
```

A five-minute smoke test on a fresh project, without an agent:

```bash
bash .specify/scripts/bash/create-new-feature.sh --json --short-name demo "Demo feature"   # specs/001-demo/ and .specify/feature.json (no git branch)
#   write specs/001-demo/spec.md with one "### User Story 1 - ..." and one "- **FR-001**: ..."
bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh inventory         # the scope contract
bash .specify/extensions/archiguard/scripts/bash/archiguard.sh scaffold handover --feature-dir specs/001-demo   # A0 reads specs/001-demo/handover.yml
bash .specify/extensions/archiguard/scripts/bash/archiguard.sh run plan a        # step A: PASS, or 'cannot evaluate' naming what is missing (handover record, lock, map, pin)
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
      - uses: rlgdev/spec-kit-guardians@v0.1.2
        with:
          features: all             # or specs/001-my-feature
```

It runs scopeGuard's check, archiGuard's CI check (every gate once on the final commit, lock drift, the ledger),
auditGuard's verify (chains, seals, evidence, the golden sources) and `guardians verify`, and writes the result
to the job summary. Each part can be switched off with `scopeguard: "false"` and so on. Make the job a required
check on the protected branch.

To compose the job yourself instead, use the three siblings' actions directly (`rlgdev/spec-kit-scopeguard@v0.4.1`,
`rlgdev/spec-kit-archiguard@v0.1.1`, `rlgdev/spec-kit-auditguard@v0.1.0`) and add one step:

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
| `.specify/extension-catalogs.yml`, `.specify/preset-catalogs.yml`, `.specify/bundle-catalogs.yml` | you (step 1); `guardians configure` adds Spec Kit's catalogs back to a file that lists only the Guardians' | yes |
| `.specify/presets/archiguard-templates/` | the preset install | yes |
| `.claude/skills/speckit-*/` (or your agent's folder) | Spec Kit renders the wrapped commands | yes |
| `.claude/settings.json` | Spec Kit wires the agent events (edit guard, audit guard, sessions); after a bundle install `guardians configure` has it do so | yes |
| `.specify/standards/`, `.specify/archiguard/standards.lock.yml`, `.specify/archiguard/ledger.jsonl` | you (step 3.1), `archiguard resolve`, `archiguard ledger add` | yes |
| `specs/<feature>/gates/` | the gates: verdict files, sign-off, escalation notes | yes (evidence) |
| `specs/<feature>/.scopeguard/`, `scopeguard-escalation-*.md` | scopeGuard's iteration history and escalations | the history is transient; the escalation note until decided |
| `audit/` | auditGuard; **never** by hand or by the agent | yes, always |
| `.gitattributes` | `auditguard configure` adds three lines | yes |
| `.specify/extensions/<id>/local-config.yml` (scopeGuard, archiGuard, auditGuard; Guardians has none) | you, for workstation-only overrides | no (archiGuard and auditGuard ignore it in CI; scopeGuard reads it everywhere) |

The config files, with their full reference: [scopeGuard](https://github.com/rlgdev/spec-kit-scopeguard/blob/main/config-template.yml)
(`scopeguard-config.yml`), [archiGuard](https://github.com/rlgdev/spec-kit-archiguard/blob/main/docs/configuration.md)
(`archiguard-config.yml`, `scope-config.yml`), [auditGuard](https://github.com/rlgdev/spec-kit-auditguard/blob/main/docs/configuration.md)
(`auditguard-config.yml`), [Guardians](../config-template.yml) (`guardians-config.yml`, optional). In every one
of these files (and in archiGuard's `scope-config.yml`, which scopeGuard reads) **an unknown key is an error** (exit `2`),
so a typo never switches a gate off silently; scopeGuard checks its keys this way since 0.4.1.

Environment variables for one run: `SCOPEGUARD_PYTHON` / `ARCHIGUARD_PYTHON` / `AUDITGUARD_PYTHON` /
`GUARDIANS_PYTHON` (the interpreter to use), `SCOPEGUARD_MODE=report`, `ARCHIGUARD_INTEGRATION`,
`ARCHIGUARD_MAX_ITERATIONS`, `AUDITGUARD_ACTOR`. With `CI=true`, archiGuard ignores `local-config.yml` and its
`ARCHIGUARD_*` overrides, and auditGuard ignores `local-config.yml` and `AUDITGUARD_INTEGRATION` (`AUDITGUARD_MODE`
and `AUDITGUARD_ACTOR` still apply); scopeGuard applies `local-config.yml` and `SCOPEGUARD_MODE` in CI too.

---

## 7. When something is off

| Symptom | Cause | Fix |
|---------|-------|-----|
| `scopeGuard: ERROR: no Python 3.9+ interpreter found` (any tool) | nothing usable on PATH | install Python, or set `<ID>_PYTHON=/path/to/python`; with `uv` installed the launchers also use specify-cli's Python |
| the gate runs twice in `/speckit.plan` | both the inline step and a hook are on, or both presets are installed | `guardians verify` names it; `specify preset remove scopeguard-templates`, then `guardians configure` |
| `/speckit.plan` says `skipped` for the gates | the wrapped step is off because the config says `hooks`, or the other way round | `guardians configure` (it runs every tool's configure); `[WARN] hooks_match_integration` names the tool |
| `cannot evaluate` (exit 2) in archiGuard step A | no handover record (`specs/<feature>/handover.yml`), no standards lock, no domain map, or `domain.pin` not set | step 3.1 for the standards, the lock and the pin; `archiguard scaffold handover --feature-dir specs/<feature>` for the record (in a real project the BA handover writes it); the message names the file |
| `[A4.1] A4.1 - no design authority sign-off is recorded for this feature` on `/speckit.implement` (exit 3) | implement starts only on a signed design | `archiguard signoff --by ...` on the feature branch, after plan, tasks and analyze are green and the design is committed |
| `auditguard check` reports `_unassigned` events | no sprint was open | open a sprint (3.2); the events stay where they are, as a record |
| `auditguard verify` fails `G3 unexplained_commit` | a commit touched a design artefact or code outside any recorded command (a hand edit, hooks skipped) | that is the finding; the audit trail now shows the author. Decide it with `auditguard decide` or `note` |
| `guardians verify` exits `2` with `cannot read YAML` | no PyYAML and no sibling installed | `python -m pip install pyyaml`, or run with specify-cli's Python (`GUARDIANS_PYTHON`) |
| `specify extension search` finds only the Guardians; `specify extension info git` says `Not found in catalog`; `specify extension update` skips your other extensions | a catalog file in `.specify/` replaces Spec Kit's catalogs (step 1 without its Spec Kit lines); nothing was uninstalled | `guardians configure` adds them back, or run the two Spec Kit lines of step 1 for extensions and presets |
| an agent edits a signed plan or `audit/` unhindered; no session records in `audit/` | the agent events are not wired (a bundle install does not wire them) | `guardians configure` (`[WARN] agent_events_wired` says it), or `specify extension disable guardians && specify extension enable guardians` |
| git's commit (or another extension's `after_plan` hook) did not run after `/speckit.plan` | a gate stopped the command; the output listed the hook under `NOT RUN` | resolve what the gate names and run the command again |
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

To uninstall, in this order:

```bash
specify bundle remove guardians       # removes what the bundle installed, the preset included; audit/ and your configs stay
specify extension catalog remove guardians
specify preset catalog remove guardians
specify bundle catalog remove https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/bundles.json
```

- Installed with path B? Remove the preset **first** (`specify preset remove archiguard-templates`), then the
  four extensions (`specify extension remove guardians`, `auditguard`, `archiguard`, `scopeguard`). A preset left
  behind keeps wrapping `/speckit.plan`, `/speckit.tasks` and `/speckit.implement`; they then only report
  `archiGuard not installed - skipped`.
- `catalogs: []` left in `.specify/extension-catalogs.yml` (it had no other entry) makes every
  `specify extension` catalog command fail: delete the file, and Spec Kit uses its own catalogs again.
- scopeGuard was installed before the bundle, so the bundle leaves it? Guardians set it to `integration: embedded`,
  which runs only inside archiGuard (its `configure` warns so): set `integration: inline` in
  `.specify/extensions/scopeguard/scopeguard-config.yml`, add its `scopeguard-templates` preset and run
  `bash .specify/extensions/scopeguard/scripts/bash/scopeguard.sh configure`.

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
