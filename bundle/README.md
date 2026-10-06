# Guardians bundle

One install for the three Guardians of the Spec Kit SDLC, at versions tested together:

| Component | Version | What it is |
|-----------|---------|------------|
| `scopeguard` extension | 0.4.0 | scope gates: no user story or requirement of `spec.md` is dropped by plan, tasks or implementation; runs **embedded** in archiGuard's pipeline |
| `archiguard` extension | 0.1.0 | architecture gates (domain guard, plan conformance, fitness functions, handover 4→5), the edit guard, the owner of the scope gate |
| `auditguard` extension | 0.1.0 | the tamper-evident audit trail: every command by stage, the gate reports, waivers, human decisions, out-of-band changes |
| `guardians` extension | 0.1.0 | this bundle's `configure` and `verify` |
| `archiguard-templates` preset | 0.1.0 | makes archiGuard's gates steps of `/speckit.plan`, `/speckit.tasks`, `/speckit.implement` and adds its sections to the templates |

## Install

From a Spec Kit project (Spec Kit ≥ 1.0.1):

```bash
specify extension catalog add https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/extensions.json --name guardians --install-allowed
specify preset catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/presets.json    --name guardians --install-allowed
specify bundle catalog add    https://raw.githubusercontent.com/rlgdev/spec-kit-guardians/main/catalog/bundles.json
specify bundle install guardians
```

Then configure the three together (a bundle installs; it runs nothing afterwards):

```bash
bash .specify/extensions/guardians/scripts/bash/guardians.sh configure
# Windows: .specify/extensions/guardians/scripts/powershell/guardians.ps1 configure
# or, inside your agent: /speckit.guardians.configure
```

`configure` sets scopeGuard to `integration: embedded`, adds the audit trail to archiGuard's edit guard, runs
the three tools' own `configure` commands in order, puts auditGuard's hooks first and last on the events they
share with a gate, and ends with the alignment report. `guardians verify` runs that report alone (exit `1` on a
failure) - locally and in CI.

## Notes

- A project-scoped extension catalog **replaces** Spec Kit's built-in catalogs for that project; first-party
  extensions (`bug`, `assess`, `git`) still install from the package. Add the built-in catalog again if you need
  community discovery: `specify extension catalog list` shows the stack.
- An extension already installed outside the bundle must be at the pinned version, or `bundle install` stops
  before changing anything. Remove it or install the pinned version first.
- `integration: workflow` users add the workflows by hand (`scopeguard-sdd`, `archiguard-sdd` from the
  siblings' releases); the bundle carries none.
- Upgrading: a new bundle version pins a new tested combination - `specify bundle update guardians`, then
  `guardians configure`.

Documentation and source: https://github.com/rlgdev/spec-kit-guardians
