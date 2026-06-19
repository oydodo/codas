from __future__ import annotations

import argparse
import json
from pathlib import Path

from .app.check import run_check_with_context
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
    wiki_mode.add_argument(
        "--verify",
        action="store_true",
        help="Verify committed generated Atlas sections match a fresh render (exit 1 if stale).",
    )

    init = subparsers.add_parser("init", help="Scaffold a .codas/ skeleton.")
    init.add_argument("repo", nargs="?", default=".")
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .codas files instead of skipping them.",
    )

    doctor = subparsers.add_parser("doctor", help="Diagnose Codas installation.")
    doctor.add_argument("repo", nargs="?", default=".")
    doctor.add_argument(
        "--json",
        action="store_true",
        help="Print the diagnostics as JSON.",
    )

    hooks = subparsers.add_parser("hooks", help="Install Codas git enforcement hooks.")
    hooks.add_argument("repo", nargs="?", default=".")
    hooks.add_argument(
        "--install",
        action="store_true",
        help="Install pre-commit/pre-push hooks that run `codas check`.",
    )
    hooks.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-Codas hook of the same name.",
    )
    hooks.add_argument(
        "--command",
        default="codas check .",
        help=(
            "Check command the hooks run. Default 'codas check .' assumes codas is on "
            "PATH; in a source checkout use e.g. "
            "'PYTHONPATH=src python3 -m codas check .'."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo = Path(args.repo).expanduser().resolve()

    if args.command == "check":
        report, ctx = run_check_with_context(repo)

        receipt_path = None
        if args.receipt:
            from .app.receipt import write_receipt

            receipt_path = write_receipt(repo, report)

        if args.json:
            from .app.provenance import compute_provenance

            payload = report.to_json()
            payload["provenance"] = compute_provenance(repo, ctx=ctx)
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
        from .app.wiki import (
            build_atlas_pack,
            verify_generated_sections,
            write_generated_sections,
        )

        if args.write:
            for path in write_generated_sections(repo):
                print(f"wrote {path.relative_to(repo).as_posix()}")
            return 0
        if args.verify:
            stale = verify_generated_sections(repo)
            if stale:
                for path in stale:
                    print(f"stale {path.relative_to(repo).as_posix()}")
                return 1
            print("generated sections up to date")
            return 0
        if args.emit_pack:
            print(json.dumps(build_atlas_pack(repo), indent=2, sort_keys=True))
            return 0
        parser.error("wiki: use --emit-pack, --write or --verify.")

    if args.command == "init":
        from .app.init import scaffold

        result = scaffold(repo, force=args.force)
        for rel in result.written:
            print(f"wrote {rel}")
        for rel in result.skipped:
            print(f"skipped {rel} (exists; use --force to overwrite)")
        if not result.written and not result.skipped:
            print("nothing to scaffold")
        return 0

    if args.command == "hooks":
        import sys

        from .app.hooks import install_git_hooks

        if not args.install:
            parser.error("hooks: use --install to install the git enforcement hooks.")
        result = install_git_hooks(repo, force=args.force, command=args.command)
        if result is None:
            print(
                "hooks: no usable git hooks directory (not a git repo, or core.hooksPath is invalid).",
                file=sys.stderr,
            )
            return 1
        for name in result.installed:
            print(f"installed {name} -> {result.hooks_dir}/{name}")
        for name in result.skipped:
            print(f"skipped {name} (existing non-Codas hook; pass --force to overwrite)")
        if not result.installed and not result.skipped:
            print("no hooks installed")
        return 0

    if args.command == "doctor":
        from .app.doctor import doctor_has_failures, run_doctor

        diagnostics = run_doctor(repo)
        if args.json:
            payload = [
                {"name": d.name, "status": d.status, "detail": d.detail}
                for d in diagnostics
            ]
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for d in diagnostics:
                print(f"[{d.status.upper():>4}] {d.name}: {d.detail}")
            fails = sum(1 for d in diagnostics if d.status == "fail")
            warns = sum(1 for d in diagnostics if d.status == "warn")
            print()
            if fails:
                print(f"{fails} failed, {warns} warning(s) — Codas install needs attention.")
            elif warns:
                print(f"All required checks passed, {warns} warning(s).")
            else:
                print("Codas install healthy.")
        return 1 if doctor_has_failures(diagnostics) else 0

    parser.error(f"unknown command: {args.command}")
    return 2
