from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from collections.abc import Callable

from codas.app.agents_block import verify_agents_block
from codas.config.loader import ConfigLoadError
from codas.integrations.claude import (
    ClaudeHookResult,
    install_claude_session_hook,
    verify_claude_shim,
)
from codas.integrations.enforcement import (
    DEFAULT_CHECK_COMMAND,
    InstallResult,
    install_hooks,
)
from codas.integrations.install_state import hook_state, merge_install_state
from codas.structure.loader import StructureMapError


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
    """Outcome of installing the Claude SessionStart injection hook + recording state."""

    claude: ClaudeHookResult
    agents_block: str  # current | stale | absent
    claude_shim: str  # current | stale | absent


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
    block = _doc_freshness(repo, "AGENTS.md", verify_agents_block)
    shim = _doc_freshness(repo, "CLAUDE.md", verify_claude_shim)
    merge_install_state(
        repo,
        {
            "agent_hooks": {
                "claude": {
                    "session_start": hook_state(
                        claude.status,
                        expected_command=claude.expected_command,
                        installed_command=claude.installed_command,
                        settings_path=claude.settings_path,
                        marker_id=claude.marker_id,
                        # Claude workspace-trust cannot be detected programmatically; the
                        # installer prints the approve step and the doctor reports unknown.
                        trusted="unknown",
                    )
                }
            },
            "agents_block": block,
            "claude_shim": shim,
        },
    )
    return AgentInjectionResult(claude, block, shim)
