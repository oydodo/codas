from __future__ import annotations

import shutil
from pathlib import Path

# noqa note: this module is the platform shim — it may import the neutral app/ renderer
# for text (below) but never imports codas-adapters; the facts/git seam lives in app/status.

# The neutral marker-splice + markers live in the app renderer; integrations (the platform
# shim) may import the neutral app/ renderer for its text, never the reverse (design §7).
from codas.app.agents_block import BLOCK_END, BLOCK_START, splice_managed_block

# The agent-neutral JSON-hooks machinery (design D1). This module is now the Claude-SPECIFIC
# binding over it: the .claude/settings.json path, the Claude group table, and the CLAUDE.md
# shim. HookResult is re-exported as ClaudeHookResult so existing callers (app/hooks.py) are
# unchanged.
from codas.integrations.hook_settings import (
    HookResult,
    TurnHookSpec,
    group_status,
    install_session_group,
    install_turn_groups,
    session_group_status,
)

# Back-compat alias: callers import ClaudeHookResult; the type is the neutral HookResult.
ClaudeHookResult = HookResult

# The Claude settings file, repo-relative. Codex uses ``.codex/hooks.json`` (its own module).
CLAUDE_SETTINGS_REL = ".claude/settings.json"

# Claude Code reads CLAUDE.md (not AGENTS.md). The shim is a tiny CLAUDE.md that imports
# @AGENTS.md so the Codas governance block reaches Claude. `@AGENTS.md` is plain text (not a
# backtick span or markdown link), so the scanned CLAUDE.md gains no doc_claim (must-hold #4).
_CLAUDE_SHIM_BODY = (
    "# Codas + Trellis governance\n"
    "\n"
    "This repository is governed by Codas. Read the imported governance map below: the policy\n"
    "catalog, the ownership/placement map, and the lookup protocol for querying the live atlas.\n"
    "\n"
    "@AGENTS.md\n"
)
# Portable default codas invocation for a source checkout (codas not on PATH); an installed
# codas resolves to its absolute binary. A committed settings.json must stay machine-
# independent, so the default is portable rather than a machine-absolute path.
DEFAULT_CODAS_COMMAND = "PYTHONPATH=src python3 -m codas"


def render_claude_shim() -> str:
    """The Codas-managed CLAUDE.md block (between the shared markers), deterministic."""
    return f"{BLOCK_START}\n{_CLAUDE_SHIM_BODY}{BLOCK_END}"


def claude_shim_pages(repo: Path) -> dict[Path, str]:
    """``{CLAUDE.md path: spliced content}`` — the shim block spliced into any existing
    CLAUDE.md, preserving hand content outside the markers. Shared by write/verify."""
    shim_path = repo / "CLAUDE.md"
    existing = shim_path.read_text(encoding="utf-8") if shim_path.is_file() else ""
    return {shim_path: splice_managed_block(existing, render_claude_shim())}


def write_claude_shim(repo: Path) -> list[Path]:
    """Write the CLAUDE.md shim (UTF-8 + LF pinned); return written paths (sorted)."""
    written: list[Path] = []
    for path, content in claude_shim_pages(repo).items():
        path.write_bytes(content.encode("utf-8"))
        written.append(path)
    return sorted(written)


def verify_claude_shim(repo: Path) -> list[Path]:
    """CLAUDE.md whose on-disk bytes differ from a fresh splice (stale/hand-edited/missing)."""
    stale: list[Path] = []
    for path, content in claude_shim_pages(repo).items():
        if not path.is_file() or path.read_bytes() != content.encode("utf-8"):
            stale.append(path)
    return sorted(stale)


def resolve_codas_command() -> str:
    """The base ``codas`` invocation: an installed ``codas`` on PATH (absolute, since PATH is
    unresolved in a non-interactive ``sh -c``), else the portable source-checkout module form.
    Shared by the SessionStart preflight + the baseline-record commands so they agree."""
    found = shutil.which("codas")
    return found if found else DEFAULT_CODAS_COMMAND


def resolve_agent_command(command: str | None) -> str:
    """The SessionStart preflight command. Explicit ``command`` wins; else ``<codas> preflight``."""
    if command:
        return command
    return f"{resolve_codas_command()} preflight"


def resolve_hook_runner(runner: str | None) -> str:
    """The per-turn injection entrypoint invocation. Explicit ``runner`` wins; else the SAME
    base codas invocation as SessionStart plus the neutral ``agent-hook`` subcommand — so the
    runner carries codas's OWN interpreter (the absolute console-script binary when installed,
    the PYTHONPATH=src module form in a source checkout). Routing through the CLI (not a bare
    ``python3 -m codas.integrations.agent_hook``) avoids the installed-but-different-``python3``
    failure that would raise ModuleNotFoundError at import time — BEFORE the never-raises
    guard — on every turn."""
    if runner:
        return runner
    return f"{resolve_codas_command()} agent-hook"


def baseline_record_command() -> str:
    """The SessionStart command (chained alongside preflight) that records the session
    BASELINE sha ``codas status --since-baseline`` diffs against — so a worker that COMMITS
    before returning is not invisible to the per-turn check (B1). Output redirected so the sha
    never pollutes the SessionStart context injection."""
    return f"{resolve_codas_command()} status --record-baseline > /dev/null 2>&1"


def session_hook_status(repo: Path) -> str:
    """Live state of the Claude SessionStart hook (``installed | absent | malformed``)."""
    return session_group_status(repo, CLAUDE_SETTINGS_REL)


def claude_hook_status(repo: Path, event: str, matcher: str | None) -> str:
    """Live state of a Claude per-turn group keyed by ``(event, matcher)``."""
    return group_status(repo, CLAUDE_SETTINGS_REL, event, matcher)


def install_claude_session_hook(
    repo: Path, *, command: str | None = None, force: bool = False
) -> ClaudeHookResult:
    """Merge the Codas ``SessionStart`` group into ``.claude/settings.json``. The group runs
    TWO commands: the preflight digest injection AND the baseline recorder (B1). Idempotent +
    foreign-safe (delegates to the neutral ``hook_settings`` machinery)."""
    commands = [resolve_agent_command(command), baseline_record_command()]
    return install_session_group(repo, CLAUDE_SETTINGS_REL, commands, force=force)


def turn_hook_specs() -> tuple[TurnHookSpec, ...]:
    """The per-turn injection groups (design §7 revised trigger). ``Stop`` is the universal net
    (fires when the MAIN agent yields — catches every worker, incl. mcp-codex and committed
    workers, via the baseline diff). The rest are earlier-firing optimizations; the
    ``mcp__.*codex.*`` PostToolUse matcher catches the user's preferred backend at its return."""
    return (
        TurnHookSpec("stop", "Stop", None),
        TurnHookSpec("subagent_stop", "SubagentStop", None),
        TurnHookSpec("post_tool_use_agent", "PostToolUse", "Task|Agent"),
        TurnHookSpec("post_tool_use_codex", "PostToolUse", "mcp__.*codex.*"),
        TurnHookSpec("post_tool_use_edit", "PostToolUse", "Edit|Write|MultiEdit"),
    )


def install_claude_turn_hooks(
    repo: Path, *, runner: str | None = None, force: bool = False
) -> dict[str, ClaudeHookResult]:
    """Merge the per-turn injection groups (Stop / SubagentStop / PostToolUse×3) into
    ``.claude/settings.json``. Each group runs ``agent-hook <Event>`` (the envelope
    entrypoint). Marker-guarded, idempotent, foreign-safe (neutral ``hook_settings`` core)."""
    runner = resolve_hook_runner(runner)
    return install_turn_groups(repo, CLAUDE_SETTINGS_REL, turn_hook_specs(), runner, force=force)
