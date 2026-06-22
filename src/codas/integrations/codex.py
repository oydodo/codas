"""Codex CLI integration — the Codex-specific binding over the neutral ``hook_settings`` core.

Codex CLI reads hooks from ``<repo>/.codex/hooks.json`` (the analogue of Claude Code's
``.claude/settings.json``) and consumes the SAME ``hookSpecificOutput.additionalContext``
envelope ``agent_hook`` emits. So this module is thin: it supplies the ``.codex/hooks.json``
path and the Codex group table, then delegates every merge/probe to ``hook_settings``.

Two deliberate differences from the Claude binding:

- **No shim.** Codex reads ``AGENTS.md`` natively (its ``model_instructions_file`` / project-
  instructions mechanism), so the verified AGENTS.md governance block is the static tier with
  no per-agent file — there is no ``.codex`` analogue of the ``CLAUDE.md`` shim.
- **Per-turn carriers (codex review B1+B2).** ``UserPromptSubmit`` is the PRIMARY carrier —
  Codex documents it as a context-injection event, it fires every prompt, and ``inject_context``
  reads the git changed-file set so it catches EVERY edit regardless of tool (``apply_patch``,
  ``Edit``/``Write``, or shell/``unified_exec`` writes that bypass a tool matcher).
  ``PostToolUse`` (matcher ``apply_patch|Edit|Write``) adds immediate edit feedback.
  ``Stop``/``SubagentStop`` are deliberately OMITTED — Codex docs do not confirm those events
  accept injected ``additionalContext`` (they carry continuation/block semantics); add them
  only once an integration test against a real Codex CLI proves the envelope is accepted.
"""
from __future__ import annotations

from pathlib import Path

from codas.integrations.hook_settings import (
    HookResult,
    TurnHookSpec,
    baseline_record_command,
    group_status,
    install_session_group,
    install_turn_groups,
    resolve_hook_runner,
    resolve_preflight_command,
    session_group_status,
)

# The Codex hook file, repo-relative. Per-machine install artifact (gitignored + in
# structure.index._IGNORE_PATHS + app/hooks._SCRATCH_IGNORES), so a Codex install never moves
# the byte-identical inventory.
CODEX_SETTINGS_REL = ".codex/hooks.json"


def codex_turn_specs() -> tuple[TurnHookSpec, ...]:
    """The Codex per-turn injection groups (codex review B1+B2). ``UserPromptSubmit`` is the
    primary carrier (documented injector; catches all edits incl. shell/``unified_exec`` since
    ``inject_context`` reads the git diff). ``PostToolUse`` adds immediate edit feedback.
    ``Stop``/``SubagentStop`` are omitted until proven on a real Codex CLI."""
    return (
        TurnHookSpec("user_prompt_submit", "UserPromptSubmit", None),
        TurnHookSpec("post_tool_use_edit", "PostToolUse", "apply_patch|Edit|Write"),
    )


def codex_session_status(repo: Path) -> str:
    """Live state of the Codex SessionStart hook (``installed | absent | malformed``)."""
    return session_group_status(repo, CODEX_SETTINGS_REL)


def codex_hook_status(repo: Path, event: str, matcher: str | None) -> str:
    """Live state of a Codex per-turn group keyed by ``(event, matcher)``."""
    return group_status(repo, CODEX_SETTINGS_REL, event, matcher)


def install_codex_session_hook(
    repo: Path, *, command: str | None = None, force: bool = False
) -> HookResult:
    """Merge the Codas ``SessionStart`` group into ``.codex/hooks.json``. The group runs TWO
    commands: the preflight digest (its stdout becomes Codex developer context) AND the baseline
    recorder (B1, stdout suppressed). Idempotent + foreign-safe (neutral ``hook_settings`` core)."""
    commands = [resolve_preflight_command(command), baseline_record_command()]
    return install_session_group(repo, CODEX_SETTINGS_REL, commands, force=force)


def install_codex_turn_hooks(
    repo: Path, *, runner: str | None = None, force: bool = False
) -> dict[str, HookResult]:
    """Merge the per-turn injection groups (UserPromptSubmit + PostToolUse) into
    ``.codex/hooks.json``. Each group runs ``agent-hook <Event>`` (the shared envelope
    entrypoint). Marker-guarded, idempotent, foreign-safe."""
    runner = resolve_hook_runner(runner)
    return install_turn_groups(repo, CODEX_SETTINGS_REL, codex_turn_specs(), runner, force=force)
