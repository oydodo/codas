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
        "--emit-tree",
        action="store_true",
        help="Print the neutral Codas knowledge tree (verified facts) as JSON.",
    )
    wiki_mode.add_argument(
        "--emit-feed",
        action="store_true",
        help="Print the W3 semantic FEED (knowledge tree + grounding instructions) as JSON.",
    )
    wiki_mode.add_argument(
        "--calibrate",
        action="store_true",
        help="Tier the offline semantic corpus (.codas/cache/semantic/) against facts; print JSON.",
    )
    wiki_mode.add_argument(
        "--emit-mermaid",
        action="store_true",
        help="Print a Mermaid dependency graph of the product modules (verified facts).",
    )
    wiki_mode.add_argument(
        "--emit-html",
        action="store_true",
        help="Print a self-contained static HTML view of the verified facts.",
    )
    wiki_mode.add_argument(
        "--write",
        action="store_true",
        help="Write the deterministic generated Atlas sections (.codas/wiki/generated/) and the human book (wiki/).",
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
    init.add_argument(
        "--paradigm",
        default="none",
        metavar="NAME",
        help=(
            "Seed structure.yml with an architecture paradigm's nested layer units + "
            "dependency rules (planned + placeholder paths; map them to arm). Default 'none'. "
            "See `codas paradigm`."
        ),
    )
    init.add_argument(
        "--list-paradigms",
        action="store_true",
        dest="list_paradigms",
        help="List available paradigm presets and exit (alias of `codas paradigm`).",
    )

    paradigm = subparsers.add_parser(
        "paradigm", help="List available architecture paradigm presets (built-in + repo-local)."
    )
    paradigm.add_argument("repo", nargs="?", default=".")

    impact = subparsers.add_parser(
        "impact",
        help="Show what transitively calls a symbol or file (reverse reachability over call-graph facts).",
    )
    impact.add_argument(
        "target",
        help=(
            "Symbol or source path to trace callers of. A symbol may be a bare name "
            "(head_snapshot), a class-qualified method (ScanContext.head_snapshot), or "
            "a dotted name (codas.facts.snapshot.head_snapshot). A path "
            "(src/codas/facts/snapshot.py) traces callers of every symbol the file defines."
        ),
    )
    impact.add_argument("repo", nargs="?", default=".")
    impact.add_argument(
        "--json",
        action="store_true",
        help="Print the impact set as deterministic JSON.",
    )

    query = subparsers.add_parser(
        "query",
        help="Emit one inventory fact block as JSON, optionally filtered (jq-optional slice).",
    )
    query.add_argument(
        "kind",
        help="Fact block to query: symbols, imports, calls, units, tasks, doc-claims, html-claims, wiki-claims, work-items.",
    )
    query.add_argument("repo", nargs="?", default=".")
    query.add_argument(
        "--select",
        action="append",
        default=None,
        metavar="FIELD=VALUE",
        help="Keep only rows where FIELD equals VALUE, JSON-spelled (exists=true, package=null); repeatable, AND-combined.",
    )

    schema = subparsers.add_parser(
        "schema",
        help="Emit the inventory row shape (block + field names per query kind, derived from the rows present in the live inventory) as JSON.",
    )
    schema.add_argument("repo", nargs="?", default=".")

    status = subparsers.add_parser(
        "status",
        help=(
            "Advisory facts about files changed this session — the per-turn-injection "
            "core (unowned / deprecated-path / duplicate-symbol on changed files only)."
        ),
    )
    status.add_argument("repo", nargs="?", default=".")
    status.add_argument(
        "--path",
        action="append",
        default=None,
        metavar="PATH",
        help="Scope findings to this repo-relative path or prefix (repeatable).",
    )
    status_since = status.add_mutually_exclusive_group()
    status_since.add_argument(
        "--since",
        metavar="REF",
        help=(
            "Diff baseline: surface everything changed since REF (committed AND "
            "uncommitted), catching changes a worker committed before returning."
        ),
    )
    status_since.add_argument(
        "--since-baseline",
        action="store_true",
        dest="since_baseline",
        help="Use the recorded session baseline (see --record-baseline) as the diff ref.",
    )
    status_out = status.add_mutually_exclusive_group()
    status_out.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON ({path, kind, message}).",
    )
    status_out.add_argument(
        "--additional-context",
        action="store_true",
        dest="additional_context",
        help="Print the capped factual advisory string (empty when clean).",
    )
    status.add_argument(
        "--record-baseline",
        action="store_true",
        dest="record_baseline",
        help="Record current HEAD as the session baseline (for --since-baseline) and exit.",
    )

    claude_hook = subparsers.add_parser(
        "claude-hook",
        help=(
            "Internal: emit the Claude per-turn additionalContext envelope for a hook event "
            "(reads the hook input on stdin). Invoked by the installed Stop/PostToolUse hooks."
        ),
    )
    claude_hook.add_argument(
        "event",
        nargs="?",
        default="Stop",
        help="The firing hook event (Stop | SubagentStop | PostToolUse).",
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
        dest="check_command",  # NOT `command` — that dest is the subparsers' selected command
        default="codas check .",
        help=(
            "Check command the hooks run. Default 'codas check .' assumes codas is on "
            "PATH; in a source checkout use e.g. "
            "'PYTHONPATH=src python3 -m codas check .'."
        ),
    )
    hooks.add_argument(
        "--agent-command",
        default=None,
        help=(
            "Command the Claude SessionStart injection hook runs (default: an installed "
            "'codas preflight' on PATH, else the portable source-checkout form)."
        ),
    )

    agents = subparsers.add_parser(
        "agents",
        help="Render or verify the Codas agent-instruction docs (AGENTS.md block + CLAUDE.md shim).",
    )
    agents.add_argument("repo", nargs="?", default=".")
    agents_mode = agents.add_mutually_exclusive_group()
    agents_mode.add_argument(
        "--write",
        action="store_true",
        help="Write the deterministic AGENTS.md governance block + the CLAUDE.md shim.",
    )
    agents_mode.add_argument(
        "--verify",
        action="store_true",
        help="Verify the AGENTS.md block + CLAUDE.md shim match a fresh render (exit 1 if stale).",
    )

    return parser


def _print_paradigms(repo: Path) -> None:
    """Print available paradigm presets (built-in + repo-local), one per line."""
    from .app.paradigm import list_presets

    presets = list_presets(repo)
    if not presets:
        print("no paradigm presets available")
        return
    width = max(len(name) for name, _, _ in presets)
    for name, description, source in presets:
        print(f"{name.ljust(width)}  {description}  [{source}]")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # claude-hook reads the repo from the hook input on stdin (not args.repo) and must never
    # crash a turn — dispatch it BEFORE the repo resolution below, which it has no arg for.
    if args.command == "claude-hook":
        from .app.hooks import emit_claude_turn_hook

        return emit_claude_turn_hook(args.event)

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
            build_atlas_tree,
            verify_generated_sections,
            write_generated_sections,
        )

        if args.write:
            from .app.book import write_book

            written = write_generated_sections(repo) + write_book(repo)
            for path in sorted(written, key=lambda p: p.relative_to(repo).as_posix()):
                print(f"wrote {path.relative_to(repo).as_posix()}")
            return 0
        if args.verify:
            from .app.book import verify_book

            stale = verify_generated_sections(repo) + verify_book(repo)
            if stale:
                for path in sorted(stale, key=lambda p: p.relative_to(repo).as_posix()):
                    print(f"stale {path.relative_to(repo).as_posix()}")
                return 1
            print("generated sections up to date")
            return 0
        if args.emit_pack:
            print(json.dumps(build_atlas_pack(repo), indent=2, sort_keys=True))
            return 0
        if args.emit_tree:
            print(json.dumps(build_atlas_tree(repo), indent=2, sort_keys=True))
            return 0
        if args.emit_feed:
            from .app.calibrate import build_feed

            print(json.dumps(build_feed(repo), indent=2, sort_keys=True))
            return 0
        if args.calibrate:
            from .app.calibrate import run_calibrate

            print(json.dumps(run_calibrate(repo), indent=2, sort_keys=True))
            return 0
        if args.emit_mermaid:
            from .app.views import build_mermaid

            print(build_mermaid(repo), end="")
            return 0
        if args.emit_html:
            from .app.views import build_html

            print(build_html(repo), end="")
            return 0
        parser.error(
            "wiki: use --emit-pack, --emit-tree, --emit-feed, --calibrate, "
            "--emit-mermaid, --emit-html, --write or --verify."
        )

    if args.command == "paradigm":
        _print_paradigms(repo)
        return 0

    if args.command == "init":
        import sys

        from .app.init import scaffold
        from .app.paradigm import PresetError

        if args.list_paradigms:
            _print_paradigms(repo)
            return 0
        try:
            result = scaffold(repo, force=args.force, paradigm=args.paradigm)
        except PresetError as error:
            print(f"init: {error}", file=sys.stderr)
            return 1
        for rel in result.written:
            print(f"wrote {rel}")
        for rel in result.skipped:
            print(f"skipped {rel} (exists; use --force to overwrite)")
        if not result.written and not result.skipped:
            print("nothing to scaffold")
        if result.paradigm:
            print(
                f"seeded paradigm '{result.paradigm}' as planned units in "
                ".codas/structure.yml (rename the example context + map paths to arm)."
            )
            if result.advisory:
                print(
                    "WARNING: this repo's ecosystem has no Python import resolver — "
                    "dependency_direction will NOT enforce this paradigm (advisory only).",
                    file=sys.stderr,
                )
        return 0

    if args.command == "hooks":
        import sys

        from .app.hooks import install_agent_injection, install_git_hooks

        if not args.install:
            parser.error("hooks: use --install to install the git enforcement hooks.")
        result = install_git_hooks(repo, force=args.force, command=args.check_command)
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

        # Claude Code SessionStart injection hook (the norm-injection seam, gaps 2/3).
        agent = install_agent_injection(repo, command=args.agent_command, force=args.force)
        claude = agent.claude
        ran = claude.installed_command or claude.expected_command
        print(f"claude session hook: {claude.status} -> {claude.settings_path} ({ran})")
        turn = agent.turn_hooks
        live = sum(1 for r in turn.values() if r.status in ("installed", "refreshed"))
        print(
            f"claude per-turn hooks: {live}/{len(turn)} groups "
            "(Stop, SubagentStop, PostToolUse: Agent/codex/edit)"
        )
        if claude.status in ("installed", "refreshed"):
            print("  approve the hooks in Claude Code when prompted (workspace trust).")
        if agent.agents_block != "current" or agent.claude_shim != "current":
            print(
                f"  agent docs: AGENTS.md block {agent.agents_block}, CLAUDE.md shim "
                f"{agent.claude_shim} — run `codas agents --write`."
            )
        return 0

    if args.command == "agents":
        from .app.agent_docs import verify_agent_docs, write_agent_docs

        if args.write:
            for path in write_agent_docs(repo):
                print(f"wrote {path.relative_to(repo).as_posix()}")
            return 0
        if args.verify:
            stale = verify_agent_docs(repo)
            if stale:
                for path in stale:
                    print(f"stale {path.relative_to(repo).as_posix()}")
                return 1
            print("agent docs up to date")
            return 0
        parser.error("agents: use --write or --verify.")

    if args.command == "query":
        import sys

        from .app.query import QueryError, parse_selectors, run_query

        try:
            selectors = parse_selectors(args.select or [])
            rows = run_query(repo, args.kind, selectors)
        except QueryError as error:
            print(f"query: {error}", file=sys.stderr)
            return 2
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0

    if args.command == "schema":
        from .app.query import run_schema

        print(json.dumps(run_schema(repo), indent=2, sort_keys=True))
        return 0

    if args.command == "impact":
        from .app.impact import render_impact_text, run_impact

        result = run_impact(repo, args.target)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(render_impact_text(result))
        return 0

    if args.command == "status":
        from .app.status import (
            read_baseline,
            record_baseline,
            render_additional_context,
            render_text,
            run_status,
        )

        if args.record_baseline:
            sha = record_baseline(repo)
            print(sha or "no git baseline")
            return 0
        since = read_baseline(repo) if args.since_baseline else args.since
        result = run_status(repo, paths=tuple(args.path or ()), since=since)
        if args.json:
            print(json.dumps(list(result.findings), indent=2, sort_keys=True))
        elif args.additional_context:
            text = render_additional_context(result)
            if text:
                print(text)
        else:
            print(render_text(result))
        return 0  # advisory: status never sets a non-zero exit.

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
