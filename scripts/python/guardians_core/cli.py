"""Command line: guardians configure | verify | version."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .common import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, GuardiansError, configure_stdout, find_root
from .config import load_config
from .siblings import Project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardians",
        description="One cover for scopeGuard, archiGuard and auditGuard: configure the three together and verify that "
                    "their configurations agree.",
        epilog="Exit codes: 0 ok | 1 verify found a failure (configure: one remains after it ran) | 2 cannot run")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, help="Spec Kit project root (default: the nearest ancestor with .specify/)")
    common.add_argument("--config", type=Path, help="guardians-config.yml to use (default: the installed one, or built-in defaults)")
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--verbose", action="store_true", help="show the siblings' full configure output")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("configure", parents=[common],
                       help="cross-wire the three, run their configures in order, order their hooks, show what is in force")
    p.add_argument("--dry-run", action="store_true", help="show what would change, change nothing (passed to the siblings)")
    p.add_argument("--no-siblings", action="store_true", help="skip the siblings' own configure commands")
    sub.add_parser("verify", parents=[common], help="check that the three Guardians' configurations agree")
    sub.add_parser("version", parents=[common], help="print the version")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_stdout()
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(json.dumps({"tool": "guardians", "version": __version__}) if args.json else f"Guardians {__version__}")
        return EXIT_OK
    try:
        root = find_root(args.root)
        project = Project(root)
        cfg = load_config(root, args.config)
        if args.command == "verify":
            from .verify import header, run_verify

            report = run_verify(project, cfg)
            if args.json:
                print(json.dumps(report.data(), indent=2, ensure_ascii=False))
            else:
                print(header(root, "verify"))
                print("")
                print(report.text())
            return EXIT_FINDINGS if report.failed else EXIT_OK
        if args.command == "configure":
            from .configure import run_configure

            text, outcome = run_configure(project, cfg, args.dry_run, not args.no_siblings, args.verbose)
            print(json.dumps(outcome.data(), indent=2, ensure_ascii=False) if args.json else text)
            return outcome.exit_code
    except GuardiansError as exc:
        print(f"Guardians: ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
