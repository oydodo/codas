from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app.check import run_check
from .reporting.console import print_context_pack, print_findings


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
    check.add_argument(
        "--receipt",
        action="store_true",
        help="Write a durable run receipt under .codas/receipts/.",
    )

    inventory = subparsers.add_parser("inventory", help="Build a Codas inventory.")
    inventory.add_argument("repo", nargs="?", default=".")
    inventory.add_argument(
        "--json",
        action="store_true",
        help="Print the normalized Atlas inventory as JSON.",
    )

    preflight = subparsers.add_parser("preflight", help="Generate task preflight context.")
    preflight.add_argument("repo", nargs="?", default=".")
    preflight.add_argument("--task", help="Task id to assemble context for.")
    preflight.add_argument(
        "--json",
        action="store_true",
        help="Print the context pack as JSON.",
    )

    wiki = subparsers.add_parser("wiki", help="Generate or verify Atlas Wiki.")
    wiki.add_argument("repo", nargs="?", default=".")
    wiki_mode = wiki.add_mutually_exclusive_group()
    wiki_mode.add_argument(
        "--emit-pack",
        action="store_true",
        help="Print the Atlas grounding pack (verified facts) as JSON.",
    )
    wiki_mode.add_argument(
        "--write",
        action="store_true",
        help="Write the deterministic generated Atlas sections under .codas/wiki/generated/.",
    )

    doctor = subparsers.add_parser("doctor", help="Diagnose Codas installation.")
    doctor.add_argument("repo", nargs="?", default=".")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve()

    if args.command == "check":
        report = run_check(repo)

        receipt_path = None
        if args.receipt:
            from .app.receipt import write_receipt

            receipt_path = write_receipt(repo, report)

        if args.json:
            from .app.provenance import compute_provenance

            payload = report.to_json()
            payload["provenance"] = compute_provenance(repo)
            if receipt_path is not None:
                payload["receipt"] = str(receipt_path)
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print_findings(report.findings)
            if receipt_path is not None:
                print(f"Receipt written: {receipt_path}")
        if not args.no_exit_code and report.has_errors:
            return 1
        return 0

    if args.command == "inventory":
        from .app.inventory import (
            render_inventory_json,
            render_inventory_summary,
            run_inventory,
        )

        inventory = run_inventory(repo)
        if args.json:
            print(render_inventory_json(inventory))
        else:
            print(render_inventory_summary(inventory))
        return 0

    if args.command == "preflight":
        import sys

        from .app.preflight import build_context_pack
        from .config.loader import ConfigLoadError
        from .structure.loader import StructureMapError

        try:
            pack = build_context_pack(repo, task_id=args.task)
        except (ConfigLoadError, StructureMapError) as error:
            # preflight is a precondition tool: a broken .codas can't be preflighted.
            print(f"preflight: {error}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(pack, indent=2, sort_keys=True))
        else:
            print_context_pack(pack)
        return 0

    if args.command == "wiki":
        from .app.wiki import build_atlas_pack, write_generated_sections

        if args.write:
            for path in write_generated_sections(repo):
                print(f"wrote {path.relative_to(repo).as_posix()}")
            return 0
        if args.emit_pack:
            print(json.dumps(build_atlas_pack(repo), indent=2, sort_keys=True))
            return 0
        parser.error("wiki: use --emit-pack or --write (--verify lands in a later D3 slice).")

    if args.command == "doctor":
        parser.error("doctor is planned but not implemented in P0.")

    parser.error(f"unknown command: {args.command}")
    return 2
