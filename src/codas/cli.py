from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app.check import run_check
from .reporting.console import print_findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codas",
        description="Code Atlas System for coding-agent-maintained repositories.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Run Codas policy checks.")
    check.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Repository root to check. Defaults to the current directory.",
    )
    check.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON report.",
    )
    check.add_argument(
        "--no-exit-code",
        action="store_true",
        help="Always exit 0, even when error findings are present.",
    )

    inventory = subparsers.add_parser("inventory", help="Build a Codas inventory.")
    inventory.add_argument("repo", nargs="?", default=".")

    preflight = subparsers.add_parser("preflight", help="Generate task preflight context.")
    preflight.add_argument("repo", nargs="?", default=".")
    preflight.add_argument("--task", help="Task path or name.")

    wiki = subparsers.add_parser("wiki", help="Generate or verify Atlas Wiki.")
    wiki.add_argument("repo", nargs="?", default=".")

    doctor = subparsers.add_parser("doctor", help="Diagnose Codas installation.")
    doctor.add_argument("repo", nargs="?", default=".")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve()

    if args.command == "check":
        report = run_check(repo)
        if args.json:
            print(json.dumps(report.to_json(), indent=2, sort_keys=True))
        else:
            print_findings(report.findings)
        if not args.no_exit_code and report.has_errors:
            return 1
        return 0

    if args.command in {"inventory", "preflight", "wiki", "doctor"}:
        parser.error(f"{args.command} is planned but not implemented in P0.")

    parser.error(f"unknown command: {args.command}")
    return 2
