from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from collections.abc import Callable

from codas.app.agents_block import verify_agents_block
from codas.config.loader import ConfigLoadError
from codas.integrations.claude import verify_claude_shim
from codas.integrations.enforcement import (
    DEFAULT_CHECK_COMMAND,
    InstallResult,
    install_hooks,
)
from codas.integrations.hook_settings import HookResult
from codas.integrations.install_state import (
    hook_state,
    merge_install_state,
    read_install_state,
)
from codas.integrations.registry import select_agents
from codas.structure.loader import StructureMapError


def emit_agent_turn_hook(event: str) -> int:
    """App-layer bridge for the ``codas agent-hook <Event>`` CLI subcommand (the CLI may not
    import ``role-integrations``; this layer is the permitted bridge). Delegates to the
    integrations envelope entrypoint, which reads the hook input from stdin and prints the
    agent-neutral ``additionalContext`` envelope. Always returns 0 (the never-block invariant)."""
    from codas.integrations.agent_hook import run_agent_hook

    return run_agent_hook([event])


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
class AgentInstall:
    """One agent's injection-install outcome: the SessionStart group + the per-turn groups."""

    name: str
    session: HookResult  # the SessionStart preflight + baseline group
    turn_hooks: dict[str, HookResult]  # the per-turn injection groups (gap 3)
    has_shim: bool


@dataclass(frozen=True)
class AgentInjectionResult:
    """Outcome of installing the injection hooks for one or more agents + recording state."""

    installs: tuple[AgentInstall, ...]  # one per installed agent (claude, codex, …)
    agents_block: str  # current | stale | absent
    claude_shim: str  # current | stale | absent


# Machine-local scratch the installers write — must be gitignored on the consumer repo, or
# `git ls-files --others` surfaces them as "changed" (polluting `codas status`) and the user
# might commit a per-machine marker. Kept in sync with structure.index._IGNORE_PATHS + .gitignore.
_SCRATCH_IGNORES = (
    ".codas/.install-state.json",
    ".codas/.status-seen.json",
    ".codex/hooks.json",
)


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


def _agent_hook_state(session: HookResult, turn_hooks: dict[str, HookResult]) -> dict:
    """One agent's ``agent_hooks[<name>]`` slice: the SessionStart group + each per-turn group.
    ``trusted`` is ``unknown`` — workspace/repo trust cannot be detected programmatically; the
    installer prints the approve step and the doctor reports unknown."""
    state = {
        "session_start": hook_state(
            session.status,
            expected_command=session.expected_command,
            installed_command=session.installed_command,
            settings_path=session.settings_path,
            marker_id=session.marker_id,
            trusted="unknown",
        )
    }
    for key, result in turn_hooks.items():
        state[key] = hook_state(
            result.status,
            expected_command=result.expected_command,
            installed_command=result.installed_command,
            settings_path=result.settings_path,
            marker_id=result.marker_id,
            trusted="unknown",
        )
    return state


def install_agent_injection(
    repo: Path, *, command: str | None = None, force: bool = False, agents: str = "claude"
) -> AgentInjectionResult:
    """Install the SessionStart + per-turn injection hooks for the selected agent(s) and record
    the agent slice of the install-state contract (consumed by the doctor).

    App-layer bridge to the integration registry (the CLI may not import integrations). ``agents``
    is a ``--agent`` selector (``claude`` | ``codex`` | ``all``; default ``claude`` for
    back-compat — never silently write ``.codex/`` for a non-Codex user). Records each agent's
    hook state plus the freshness of the AGENTS.md block + CLAUDE.md shim. The git-hooks slice is
    written by the git installer itself (enforcement, must-hold #6); this merges the independent
    ``agent_hooks`` / ``agents_block`` / ``claude_shim`` keys, preserving the state of agents not
    installed this run.
    """
    installs: list[AgentInstall] = []
    new_state: dict[str, dict] = {}
    for integ in select_agents(agents):
        session = integ.install_session(repo, command=command, force=force)
        # Per-turn injection groups (gap 3). Disjoint events from SessionStart, so this RMW
        # preserves the group just written above.
        turn_hooks = integ.install_turn(repo, force=force)
        new_state[integ.name] = _agent_hook_state(session, turn_hooks)
        installs.append(AgentInstall(integ.name, session, turn_hooks, integ.has_shim))

    # The dedup + install-state scratch must be gitignored or it surfaces as a "changed" file.
    _ensure_gitignored(repo, _SCRATCH_IGNORES)
    block = _doc_freshness(repo, "AGENTS.md", verify_agents_block)
    shim = _doc_freshness(repo, "CLAUDE.md", verify_claude_shim)
    # Merge into the existing agent_hooks so installing one agent never drops another's state.
    existing = read_install_state(repo).get("agent_hooks")
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(new_state)
    merge_install_state(
        repo,
        {"agent_hooks": merged, "agents_block": block, "claude_shim": shim},
    )
    return AgentInjectionResult(tuple(installs), block, shim)
