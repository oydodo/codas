from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# noqa note: this module is the platform shim — it may import the neutral app/ renderer
# for text (below) but never imports codas-adapters; the facts/git seam lives in app/status.

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

# Every Codas-managed hook command (SessionStart, Stop, SubagentStop, PostToolUse) carries
# this marker as a trailing shell comment (inert when run) so re-install recognises and
# refreshes ITS OWN groups and never tramples a foreign one. Shared across all events.
SESSION_HOOK_MARKER = "codas-managed-hook"
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
    base codas invocation as SessionStart plus the ``claude-hook`` subcommand — so the runner
    carries codas's OWN interpreter (the absolute console-script binary when installed, the
    PYTHONPATH=src module form in a source checkout). This is symmetric with
    ``resolve_agent_command``; routing through the CLI (not a bare ``python3 -m
    codas.integrations.claude_hook``) avoids the installed-but-different-``python3`` failure that
    would raise ModuleNotFoundError at import time — BEFORE the never-raises guard — on every turn."""
    if runner:
        return runner
    return f"{resolve_codas_command()} claude-hook"


def _marked(command: str) -> dict:
    """A settings.json command-hook carrying the Codas marker (so re-install owns it)."""
    return {"type": "command", "command": f"{command}  # {SESSION_HOOK_MARKER}"}


def _group(matcher: str | None, commands: list[str]) -> dict:
    """One Codas hook group: a matcher-less group (SessionStart/Stop/SubagentStop) or a
    matcher-keyed group (PostToolUse). All commands in the group carry the marker."""
    hooks = [_marked(command) for command in commands]
    return {"hooks": hooks} if matcher is None else {"matcher": matcher, "hooks": hooks}


def _merge_codas_groups(data: dict, event: str, our_groups: list[dict]) -> bool:
    """Replace ALL Codas-marked groups under ``hooks[event]`` with ``our_groups`` while
    PRESERVING foreign groups (kept in order, ours appended last → deterministic, no trample).
    Returns ``True`` when ``data`` changed. Shared by the SessionStart + per-turn installers,
    which touch disjoint events, so sequential read-modify-write is safe."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks
    existing = hooks.get(event)
    existing = existing if isinstance(existing, list) else []
    foreign = [group for group in existing if not _is_ours(group)]
    new_groups = foreign + our_groups
    if new_groups == existing:
        return False
    hooks[event] = new_groups
    return True


def claude_hook_status(repo: Path, event: str, matcher: str | None) -> str:
    """Live state of a Codas hook group keyed by ``(event, matcher)``: ``installed | absent |
    malformed``. Ground truth from ``.claude/settings.json`` (read-only); the doctor calls it
    per group. Matcher matching is exact-string (a foreign group with a different matcher, or
    none, is never mistaken for ours)."""
    settings_path = repo / ".claude" / "settings.json"
    if not settings_path.is_file():
        return "absent"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "malformed"
    if not isinstance(data, dict):
        return "malformed"
    groups = (data.get("hooks") or {}).get(event)
    if not isinstance(groups, list):
        return "absent"
    for group in groups:
        if _is_ours(group) and (
            matcher is None or (isinstance(group, dict) and group.get("matcher") == matcher)
        ):
            return "installed"
    return "absent"


def _load_settings(settings_path: Path) -> dict | None:
    """The parsed ``.claude/settings.json`` mapping, ``{}`` when absent, or ``None`` when
    present-but-unparseable/non-mapping (caller returns ``malformed`` without clobbering it)."""
    if not settings_path.is_file():
        return {}
    try:
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_settings(settings_path: Path, data: dict) -> None:
    """Write the merged settings. Preserve the user's key order (json.loads keeps it); no
    sort_keys so an existing settings.json is not reshuffled. Trailing newline for a clean diff."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def baseline_record_command() -> str:
    """The SessionStart command (chained alongside preflight) that records the session
    BASELINE sha ``codas status --since-baseline`` diffs against — so a worker that COMMITS
    before returning is not invisible to the per-turn check (B1). Output redirected so the sha
    never pollutes the SessionStart context injection."""
    return f"{resolve_codas_command()} status --record-baseline > /dev/null 2>&1"


def install_claude_session_hook(
    repo: Path, *, command: str | None = None, force: bool = False
) -> ClaudeHookResult:
    """Merge the Codas ``SessionStart`` group into ``.claude/settings.json`` (JSON read-modify-
    write, never a blind text append). The group runs TWO commands: the preflight digest
    injection AND the baseline recorder (B1). Idempotent: an existing Codas group is refreshed
    in place; a foreign SessionStart group is preserved alongside. Marker-guarded so re-install
    is a no-op when unchanged.
    """
    agent_command = resolve_agent_command(command)
    settings_path = repo / ".claude" / "settings.json"
    rel = settings_path.relative_to(repo).as_posix()

    data = _load_settings(settings_path)
    if data is None:
        return ClaudeHookResult("malformed", rel, agent_command, None, SESSION_HOOK_MARKER)

    groups = (data.get("hooks") or {}).get("SessionStart")
    groups = groups if isinstance(groups, list) else []
    had_ours = any(_is_ours(group) for group in groups)
    # One Codas group, two commands: preflight (injects the digest) + baseline recorder.
    our_group = _group(None, [agent_command, baseline_record_command()])

    changed = _merge_codas_groups(data, "SessionStart", [our_group])
    # `refreshed` when a drifted Codas group is rewritten; `installed` for a fresh add / no-op.
    status = "refreshed" if (had_ours and changed) else "installed"
    if changed or force:
        _write_settings(settings_path, data)
    return ClaudeHookResult(status, rel, agent_command, agent_command, SESSION_HOOK_MARKER)


@dataclass(frozen=True)
class TurnHookSpec:
    """One per-turn injection hook group: where it fires (``event`` + optional ``matcher``),
    which ``hookEventName`` the envelope echoes (== ``event``), and its install-state ``key``."""

    key: str
    event: str
    matcher: str | None


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
    ``.claude/settings.json``. Each group runs ``claude_hook <Event>`` (the envelope
    entrypoint). Marker-guarded, idempotent, foreign-safe. Returns ``{key: ClaudeHookResult}``;
    a single ``{"_": malformed}`` result when settings.json is unparseable.

    Touches events disjoint from the SessionStart installer, so calling both in sequence is
    safe (each preserves the other's groups). Sorted-key dict for deterministic install-state."""
    runner = resolve_hook_runner(runner)
    settings_path = repo / ".claude" / "settings.json"
    rel = settings_path.relative_to(repo).as_posix()

    data = _load_settings(settings_path)
    if data is None:
        return {"_": ClaudeHookResult("malformed", rel, None, None, SESSION_HOOK_MARKER)}

    specs = turn_hook_specs()
    by_event: dict[str, list[TurnHookSpec]] = {}
    for spec in specs:
        by_event.setdefault(spec.event, []).append(spec)

    changed = False
    results: dict[str, ClaudeHookResult] = {}
    for event, event_specs in by_event.items():
        existing = (data.get("hooks") or {}).get(event)
        existing = existing if isinstance(existing, list) else []
        had_ours = any(_is_ours(group) for group in existing)
        our_groups = [
            _group(spec.matcher, [f"{runner} {spec.event}"]) for spec in event_specs
        ]
        event_changed = _merge_codas_groups(data, event, our_groups)
        if event_changed:
            changed = True
        for spec in event_specs:
            command = f"{runner} {spec.event}"
            # `refreshed` only when a drifted Codas group was actually rewritten; a byte-identical
            # re-install reports `installed` (matches the SessionStart contract).
            status = "refreshed" if (had_ours and event_changed) else "installed"
            results[spec.key] = ClaudeHookResult(
                status, rel, command, command, SESSION_HOOK_MARKER
            )
    if changed or force:
        _write_settings(settings_path, data)
    return results
