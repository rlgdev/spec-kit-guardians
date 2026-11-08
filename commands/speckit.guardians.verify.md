---
description: "Guardians: check that the scopeGuard, archiGuard and auditGuard configurations agree"
scripts:
  sh: bash scripts/bash/guardians.sh verify
  ps: scripts/powershell/guardians.ps1 verify
  py: scripts/python/guardians.py verify
---

## User Input

```text
$ARGUMENTS
```

## Goal

Report, without changing anything, whether the three Guardians agree: all installed at versions they accept from
each other, the preset matching archiGuard's integration, scopeGuard embedded under archiGuard, auditGuard's
hooks first and last on shared events, one base branch, the edit guard covering the audit trail, the agent
events wired, modes, `.gitattributes` and CODEOWNERS, and Spec Kit's catalogs still in the project's catalog files.

## Steps

1. Run `{SCRIPT}` from the repository root and show the output as is. Exit code `0` = aligned (warnings
   possible); `1` = at least one `[FAIL]`.
2. For every `[WARN]` and `[FAIL]`, quote its `fix:` line. When the fix is `guardians configure`, offer to run
   `__SPECKIT_COMMAND_GUARDIANS_CONFIGURE__`; when it names two files that disagree, the user decides.
3. Never edit the three tools' config files or `.specify/extensions.yml` to make a finding go away.
