from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# The neutral marker-splice + markers live in the app renderer; integrations (the platform
# shim) may import the neutral app/ renderer for its text, never the reverse (design §7).
from codas.app.agents_block import BLOCK_END, BLOCK_START, splice_managed_block

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

# A SessionStart hook command carries this marker (a trailing shell comment, inert when run)
# so re-install recognises and refreshes ITS OWN hook and never tramples a foreign one.
SESSION_HOOK_MARKER = "codas-managed-hook"
# Portable default: works in a source checkout (codas not on PATH). An installed codas can pass
# `--agent-command "codas preflight"`. A committed settings.json must stay machine-independent,
# so the default is portable rather than a machine-absolute path.
DEFAULT_AGENT_COMMAND = "PYTHONPATH=src python3 -m codas preflight"


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


@dataclass(frozen=True)
class ClaudeHookResult:
    """Outcome of the SessionStart hook install — the install-state contract surface for the
    1/4 doctor task. ``status`` ∈ installed | refreshed | skipped | foreign | malformed."""

    status: str
    settings_path: str
    expected_command: str
    installed_command: str | None
    marker_id: str


def _is_ours(group: object) -> bool:
    """True if a SessionStart matcher-group is one Codas installed (any inner hook command
    carries the marker). A foreign group is never mistaken for ours and never trampled."""
    if not isinstance(group, dict):
        return False
    for hook in group.get("hooks") or ():
        if isinstance(hook, dict) and SESSION_HOOK_MARKER in str(hook.get("command") or ""):
            return True
    return False


def session_hook_status(repo: Path) -> str:
    """Live state of the Claude SessionStart hook: ``installed | absent | malformed`` (ground
    truth). Loads ``.claude/settings.json`` and scans ``hooks.SessionStart`` for a Codas-marked
    group with the same ``_is_ours`` check the installer uses. Missing file → ``absent``;
    unparseable / non-mapping → ``malformed``. Read-only; cannot probe workspace-trust (that
    rides in ``.install-state.json`` as ``trusted``)."""
    settings_path = repo / ".claude" / "settings.json"
    if not settings_path.is_file():
        return "absent"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "malformed"
    if not isinstance(data, dict):
        return "malformed"
    groups = (data.get("hooks") or {}).get("SessionStart")
    if isinstance(groups, list) and any(_is_ours(group) for group in groups):
        return "installed"
    return "absent"


def resolve_agent_command(command: str | None) -> str:
    """The SessionStart command. Explicit ``command`` wins; else an installed ``codas`` on PATH
    (absolute, since PATH is unresolved in a non-interactive ``sh -c``); else the portable
    source-checkout default."""
    if command:
        return command
    found = shutil.which("codas")
    return f"{found} preflight" if found else DEFAULT_AGENT_COMMAND


def install_claude_session_hook(
    repo: Path, *, command: str | None = None, force: bool = False
) -> ClaudeHookResult:
    """Merge a Codas ``SessionStart`` hook into ``.claude/settings.json`` (JSON read-modify-
    write, never a blind text append). Idempotent: an existing Codas hook is refreshed in
    place; a foreign SessionStart group is preserved alongside. Marker-guarded so re-install is
    a no-op when the command is unchanged.
    """
    agent_command = resolve_agent_command(command)
    marked = f"{agent_command}  # {SESSION_HOOK_MARKER}"
    settings_path = repo / ".claude" / "settings.json"
    rel = settings_path.relative_to(repo).as_posix()

    data: dict
    if settings_path.is_file():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ClaudeHookResult("malformed", rel, agent_command, None, SESSION_HOOK_MARKER)
        if not isinstance(loaded, dict):
            return ClaudeHookResult("malformed", rel, agent_command, None, SESSION_HOOK_MARKER)
        data = loaded
    else:
        data = {}

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    groups = hooks.get("SessionStart")
    if not isinstance(groups, list):
        groups = []

    ours = [g for g in groups if _is_ours(g)]
    foreign = [g for g in groups if not _is_ours(g)]
    our_group = {"hooks": [{"type": "command", "command": marked}]}

    # Foreign groups kept in order, our (single, fresh) group last -> deterministic + no trample.
    new_groups = foreign + [our_group]
    already_current = new_groups == groups
    # `refreshed` when a drifted Codas hook is rewritten; `installed` for a fresh add or no-op.
    status = "refreshed" if (ours and not already_current) else "installed"
    if already_current and not force:
        # Already current -> no rewrite (idempotent, no byte churn).
        return ClaudeHookResult(status, rel, agent_command, agent_command, SESSION_HOOK_MARKER)

    hooks["SessionStart"] = new_groups
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the user's key order (json.loads keeps it); only append our group. No sort_keys
    # so an existing settings.json is not reshuffled. Trailing newline for a clean diff.
    settings_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return ClaudeHookResult(status, rel, agent_command, agent_command, SESSION_HOOK_MARKER)
