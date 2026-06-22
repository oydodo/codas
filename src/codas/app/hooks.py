from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from collections.abc import Callable

from codas.app.agents_block import verify_agents_block
from codas.config.loader import ConfigLoadError
from codas.integrations.claude import (
    ClaudeHookResult,
    install_claude_session_hook,
    install_claude_turn_hooks,
    verify_claude_shim,
)
from codas.integrations.enforcement import (
    DEFAULT_CHECK_COMMAND,
    InstallResult,
    install_hooks,
)
from codas.integrations.install_state import hook_state, merge_install_state
from codas.structure.loader import StructureMapError


def emit_claude_turn_hook(event: str) -> int:
    """App-layer bridge for the ``codas claude-hook <Event>`` CLI subcommand (the CLI may not
    import ``role-integrations``; this layer is the permitted bridge). Delegates to the
    integrations envelope entrypoint, which reads the hook input from stdin and prints the
    Claude ``additionalContext`` envelope. Always returns 0 (the never-block invariant)."""
    from codas.integrations.claude_hook import run_claude_hook

    return run_claude_hook([event])


def install_git_hooks(
    repo: Path, *, force: bool = False, command: str = DEFAULT_CHECK_COMMAND
) -> InstallResult | None:
    """Install Codas git enforcement hooks (thin app-layer orchestration).

    The §11/dependency boundary forbids the CLI umbrella (``codas-source``) from
    importing ``role-integrations`` directly; the app orchestration layer is the
    permitted bridge (``codas-app`` may depend on integrations). The CLI calls this and
    reads the returned ``InstallResult`` without importing the integration itself.
    Delegates to :func:`codas.integrations.enforcement.install_hooks`; returns ``None``
    if ``repo`` has no usable git hooks directory. ``command`` is the check command the
    hooks run (override it where ``codas`` is not on PATH, e.g. a source checkout).
    """
    return install_hooks(repo, force=force, command=command)


@dataclass(frozen=True)
class AgentInjectionResult:
    """Outcome of installing the Claude injection hooks + recording state."""

    claude: ClaudeHookResult  # the SessionStart preflight + baseline group
    agents_block: str  # current | stale | absent
    claude_shim: str  # current | stale | absent
    turn_hooks: dict[str, ClaudeHookResult]  # the per-turn injection groups (gap 3)


# Machine-local scratch the installers write — must be gitignored on the consumer repo, or
# `git ls-files --others` surfaces them as "changed" (polluting `codas status`) and the user
# might commit a per-machine marker. Kept in sync with structure.index._IGNORE_PATHS + .gitignore.
_SCRATCH_IGNORES = (".codas/.install-state.json", ".codas/.status-seen.json")


def _ensure_gitignored(repo: Path, patterns: tuple[str, ...]) -> None:
    """Append each missing pattern to the repo's ``.gitignore`` (idempotent, best-effort —
    never raises). A no-op when every pattern is already present."""
    try:
        path = repo / ".gitignore"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        present = {line.strip() for line in existing.splitlines()}
        missing = [pattern for pattern in patterns if pattern not in present]
        if not missing:
            return
        text = existing if existing.endswith("\n") or not existing else existing + "\n"
        text += "".join(f"{pattern}\n" for pattern in missing)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def _doc_freshness(
    repo: Path, filename: str, verify: Callable[[Path], list[Path]]
) -> str:
    """A rendered doc's state for the install-state contract: ``absent`` when the file is
    missing OR the governance sources needed to render it are missing/broken, ``stale`` when
    present-but-drifted, else ``current``. Degrades (never raises) so bundling agent-hook
    install with a half-configured repo records state instead of crashing."""
    if not (repo / filename).is_file():
        return "absent"
    try:
        stale = verify(repo)
    except (ConfigLoadError, StructureMapError):
        return "absent"
    return "stale" if stale else "current"


def install_agent_injection(
    repo: Path, *, command: str | None = None, force: bool = False
) -> AgentInjectionResult:
    """Install the Claude Code SessionStart injection hook and record the agent slice of the
    install-state contract (consumed by the 1/4 doctor task).

    App-layer bridge to ``integrations/claude`` (the CLI may not import it). Records the
    SessionStart hook state plus the freshness of the AGENTS.md block + CLAUDE.md shim, so the
    doctor can later report installed-but-stale or installed-but-untrusted. The git-hooks slice
    is written by the git installer itself (enforcement, must-hold #6); this merges the
    independent ``agent_hooks`` / ``agents_block`` / ``claude_shim`` keys.
    """
    claude = install_claude_session_hook(repo, command=command, force=force)
    # Per-turn injection groups (gap 3): Stop / SubagentStop / PostToolUse×3. Disjoint events
    # from SessionStart, so this RMW preserves the group just written above.
    turn_hooks = install_claude_turn_hooks(repo, force=force)
    # The dedup + install-state scratch must be gitignored or it surfaces as a "changed" file.
    _ensure_gitignored(repo, _SCRATCH_IGNORES)
    block = _doc_freshness(repo, "AGENTS.md", verify_agents_block)
    shim = _doc_freshness(repo, "CLAUDE.md", verify_claude_shim)
    claude_hooks_state = {
        "session_start": hook_state(
            claude.status,
            expected_command=claude.expected_command,
            installed_command=claude.installed_command,
            settings_path=claude.settings_path,
            marker_id=claude.marker_id,
            # Claude workspace-trust cannot be detected programmatically; the installer
            # prints the approve step and the doctor reports unknown.
            trusted="unknown",
        )
    }
    for key, result in turn_hooks.items():
        claude_hooks_state[key] = hook_state(
            result.status,
            expected_command=result.expected_command,
            installed_command=result.installed_command,
            settings_path=result.settings_path,
            marker_id=result.marker_id,
            trusted="unknown",
        )
    merge_install_state(
        repo,
        {
            "agent_hooks": {"claude": claude_hooks_state},
            "agents_block": block,
            "claude_shim": shim,
        },
    )
    return AgentInjectionResult(claude, block, shim, turn_hooks)
