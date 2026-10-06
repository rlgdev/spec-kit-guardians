#!/usr/bin/env python3
"""Guardians - one cover for scopeGuard, archiGuard and auditGuard (launcher for the engine in guardians_core/).

    python .specify/extensions/guardians/scripts/python/guardians.py <command> [options]

Standard library only, Python 3.9+. Exit codes: 0 ok, 1 verify found a failure, 2 cannot run.
"""

import sys
from pathlib import Path

# The engine lives in .specify/extensions/guardians/, which the project commits: never write __pycache__ there.
sys.dont_write_bytecode = True

if sys.version_info < (3, 9):
    sys.stderr.write("Guardians: ERROR: Python 3.9 or newer is required\n")
    sys.exit(2)

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from guardians_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
