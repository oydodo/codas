"""The agent-integration registry — the seam the second agent (Codex) unlocked.

Before this, ``"claude"`` was hardcoded at the install/doctor/CLI sites. Each supported agent
is now one :class:`AgentIntegration` descriptor binding the neutral ``hook_settings`` core to a
settings path + a per-agent group table + (optionally) a shim. The orchestration in
``app/hooks`` and the diagnostics in ``app/doctor`` iterate the registry; adding a third agent
is one entry here plus its thin installer module — no new dispatch sites.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from codas.integrations import claude, codex
from codas.integrations.hook_settings import HookResult, TurnHookSpec


@dataclass(frozen=True)
class AgentIntegration:
    """One agent's binding over the neutral hook machinery. ``has_shim`` is True only for an
    agent that needs a per-agent instruction file (Claude's ``CLAUDE.md``); agents that read
    ``AGENTS.md`` natively (Codex) carry no shim."""

    name: str
    settings_rel: str
    install_session: Callable[..., HookResult]  # (repo, *, command, force) -> HookResult
    install_turn: Callable[..., dict[str, HookResult]]  # (repo, *, runner, force) -> {key: HookResult}
    session_status: Callable[[Path], str]  # (repo) -> installed|absent|malformed
    hook_status: Callable[[Path, str, "str | None"], str]  # (repo, event, matcher) -> status
    turn_specs: Callable[[], tuple[TurnHookSpec, ...]]
    has_shim: bool


CLAUDE = AgentIntegration(
    name="claude",
    settings_rel=claude.CLAUDE_SETTINGS_REL,
    install_session=claude.install_claude_session_hook,
    install_turn=claude.install_claude_turn_hooks,
    session_status=claude.session_hook_status,
    hook_status=claude.claude_hook_status,
    turn_specs=claude.turn_hook_specs,
    has_shim=True,
)

CODEX = AgentIntegration(
    name="codex",
    settings_rel=codex.CODEX_SETTINGS_REL,
    install_session=codex.install_codex_session_hook,
    install_turn=codex.install_codex_turn_hooks,
    session_status=codex.codex_session_status,
    hook_status=codex.codex_hook_status,
    turn_specs=codex.codex_turn_specs,
    has_shim=False,
)

# Keyed by name; insertion order is the install/report order. ``all`` selects every value.
AGENTS: dict[str, AgentIntegration] = {"claude": CLAUDE, "codex": CODEX}

# The CLI ``--agent`` choices. ``all`` is the explicit opt-in to install every agent; the
# default is ``claude`` (back-compat — never silently write ``.codex/`` for a non-Codex user,
# codex review OQ4).
AGENT_CHOICES = ("claude", "codex", "all")


def select_agents(selector: str) -> tuple[AgentIntegration, ...]:
    """The integrations named by a ``--agent`` selector. ``all`` → every registered agent; a
    name → that one (empty tuple for an unknown name, which the CLI rejects via ``choices``)."""
    if selector == "all":
        return tuple(AGENTS.values())
    integ = AGENTS.get(selector)
    return (integ,) if integ is not None else ()
