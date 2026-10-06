---
description: "Guardians: configure scopeGuard, archiGuard and auditGuard together and show what is in force"
scripts:
  sh: bash scripts/bash/guardians.sh configure
  ps: scripts/powershell/guardians.ps1 configure
  py: scripts/python/guardians.py configure
---

## User Input

```text
$ARGUMENTS
```

## Goal

One configure for the family: set scopeGuard to `integration: embedded` (archiGuard runs the scope gate), add
the audit trail to archiGuard's edit guard, run the three tools' own `configure` commands in order, give
auditGuard's hooks the first and last place on the events it shares with a gate, and print one table of what is
in force with the alignment checks.

## Steps

1. Run `{SCRIPT}` from the repository root. Append `--dry-run` if the user only wants to see what would change.
2. Show the output as is. Exit code `0` = configured and aligned; `1` = a `[FAIL]` remains; `2` = a sibling's
   configure failed or a file could not be read (its output is shown - stop there).
3. A remaining `[FAIL]` names a decision for a person (for example `git_base_agrees`: two files name different
   base branches). Tell the user which files disagree and what each says. Do not pick a side and do not edit the
   three tools' config files or `.specify/extensions.yml` yourself: Guardians made every change that is safe to
   make without a decision.
4. `[WARN]` lines are information with a `fix:` command; quote them, do not run the fix unless asked.
