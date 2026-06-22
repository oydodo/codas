"""Agent-neutral JSON-hooks settings machinery — the shared core under the per-agent
installers (``integrations/claude.py``, ``integrations/codex.py``).

Claude Code's ``.claude/settings.json`` and Codex CLI's ``.codex/hooks.json`` carry the SAME
nested hook shape::

    {"hooks": {"<Event>": [ {"matcher"?: str, "hooks": [{"type": "command", "command": str}]} ]}}

So the marker-guarded read-modify-write (preserve foreign groups, refresh ours) is identical
for both — only the on-disk path and the per-agent group table differ. Every function here is
parameterised by ``(repo, settings_rel)`` so a second agent is a new caller, not a fork of this
logic (the extraction the Codex integration unlocked; design D1 / codex-review N4 — MOVED here,
never copied, so ``duplicate_implementation`` stays quiet).
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# Every Codas-managed hook command carries this marker as a trailing shell comment (inert when
# run) so re-install recognises and refreshes ITS OWN groups and never tramples a foreign one.
# Shared across all events AND all agents.
SESSION_HOOK_MARKER = "codas-managed-hook"

# Portable default codas invocation for a source checkout (codas not on PATH); an installed
# codas resolves to its absolute binary. A committed settings file must stay machine-
# independent, so the default is portable rather than a machine-absolute path.
DEFAULT_CODAS_COMMAND = "PYTHONPATH=src python3 -m codas"


def resolve_codas_command() -> str:
    """The base ``codas`` invocation: an installed ``codas`` on PATH (absolute, since PATH is
    unresolved in a non-interactive ``sh -c``), else the portable source-checkout module form.
    Shared by the SessionStart preflight + the baseline-record commands so they agree. Agent-
    neutral — Claude and Codex resolve the same way."""
    found = shutil.which("codas")
    return found if found else DEFAULT_CODAS_COMMAND


def resolve_preflight_command(command: str | None) -> str:
    """The SessionStart preflight command (its stdout is injected as context). Explicit
    ``command`` wins; else ``<codas> preflight``."""
    if command:
        return command
    return f"{resolve_codas_command()} preflight"


def baseline_record_command() -> str:
    """The SessionStart command (chained alongside preflight) that records the session BASELINE
    sha ``codas status --since-baseline`` diffs against — so a worker that COMMITS before
    returning is not invisible to the per-turn check (B1). Output redirected so the sha never
    pollutes the SessionStart context injection."""
    return f"{resolve_codas_command()} status --record-baseline > /dev/null 2>&1"


def resolve_hook_runner(runner: str | None) -> str:
    """The per-turn injection entrypoint invocation. Explicit ``runner`` wins; else the SAME
    base codas invocation as SessionStart plus the neutral ``agent-hook`` subcommand — so the
    runner carries codas's OWN interpreter (the absolute console-script binary when installed,
    the PYTHONPATH=src module form in a source checkout). Routing through the CLI (not a bare
    ``python3 -m codas.integrations.agent_hook``) avoids the installed-but-different-``python3``
    failure that would raise ModuleNotFoundError at import time — BEFORE the never-raises
    guard — on every turn. Agent-neutral (Claude + Codex share the ``agent-hook`` entrypoint)."""
    if runner:
        return runner
    return f"{resolve_codas_command()} agent-hook"


@dataclass(frozen=True)
class HookResult:
    """Outcome of one hook-group install — the install-state contract surface (doctor reader).
    ``status`` ∈ installed | refreshed | skipped | foreign | malformed. Agent-neutral; the
    per-agent installers return these unchanged."""

    status: str
    settings_path: str
    expected_command: str | None
    installed_command: str | None
    marker_id: str


@dataclass(frozen=True)
class TurnHookSpec:
    """One per-turn injection hook group: where it fires (``event`` + optional ``matcher``),
    which ``hookEventName`` the envelope echoes (== ``event``), and its install-state ``key``."""

    key: str
    event: str
    matcher: str | None


def _marked(command: str) -> dict:
    """A command-hook carrying the Codas marker (so re-install owns it)."""
    return {"type": "command", "command": f"{command}  # {SESSION_HOOK_MARKER}"}


def _group(matcher: str | None, commands: list[str]) -> dict:
    """One Codas hook group: a matcher-less group (SessionStart/Stop/…) or a matcher-keyed
    group (PostToolUse). All commands in the group carry the marker."""
    hooks = [_marked(command) for command in commands]
    return {"hooks": hooks} if matcher is None else {"matcher": matcher, "hooks": hooks}


def _is_ours(group: object) -> bool:
    """True if a matcher-group is one Codas installed (any inner hook command carries the
    marker). A foreign group is never mistaken for ours and never trampled."""
    if not isinstance(group, dict):
        return False
    for hook in group.get("hooks") or ():
        if isinstance(hook, dict) and SESSION_HOOK_MARKER in str(hook.get("command") or ""):
            return True
    return False


def _merge_codas_groups(data: dict, event: str, our_groups: list[dict]) -> bool:
    """Replace ALL Codas-marked groups under ``hooks[event]`` with ``our_groups`` while
    PRESERVING foreign groups (kept in order, ours appended last → deterministic, no trample).
    Returns ``True`` when ``data`` changed."""
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


def _load_settings(settings_path: Path) -> dict | None:
    """The parsed settings mapping, ``{}`` when absent, or ``None`` when present-but-
    unparseable/non-mapping (caller returns ``malformed`` without clobbering it)."""
    if not settings_path.is_file():
        return {}
    try:
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_settings(settings_path: Path, data: dict) -> None:
    """Write the merged settings. Preserve the user's key order (json.loads keeps it); no
    sort_keys so an existing file is not reshuffled. Trailing newline for a clean diff."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def session_group_status(repo: Path, settings_rel: str, event: str = "SessionStart") -> str:
    """Live state of the Codas SessionStart group: ``installed | absent | malformed`` (ground
    truth, read-only). Missing file → ``absent``; unparseable / non-mapping → ``malformed``."""
    settings_path = repo / settings_rel
    if not settings_path.is_file():
        return "absent"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "malformed"
    if not isinstance(data, dict):
        return "malformed"
    groups = (data.get("hooks") or {}).get(event)
    if isinstance(groups, list) and any(_is_ours(group) for group in groups):
        return "installed"
    return "absent"


def group_status(repo: Path, settings_rel: str, event: str, matcher: str | None) -> str:
    """Live state of a Codas hook group keyed by ``(event, matcher)``: ``installed | absent |
    malformed`` (read-only). Matcher matching is exact-string (a foreign group with a different
    matcher, or none, is never mistaken for ours)."""
    settings_path = repo / settings_rel
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


def install_session_group(
    repo: Path, settings_rel: str, commands: list[str], *, force: bool = False
) -> HookResult:
    """Merge ONE Codas ``SessionStart`` group (running ``commands`` in order) into the settings
    file (JSON read-modify-write, never a blind text append). Idempotent: an existing Codas
    group is refreshed in place; a foreign SessionStart group is preserved alongside.
    ``installed_command`` echoes the first command (the digest carrier)."""
    settings_path = repo / settings_rel
    rel = settings_path.relative_to(repo).as_posix()
    primary = commands[0] if commands else ""

    data = _load_settings(settings_path)
    if data is None:
        return HookResult("malformed", rel, primary, None, SESSION_HOOK_MARKER)

    groups = (data.get("hooks") or {}).get("SessionStart")
    groups = groups if isinstance(groups, list) else []
    had_ours = any(_is_ours(group) for group in groups)
    our_group = _group(None, list(commands))

    changed = _merge_codas_groups(data, "SessionStart", [our_group])
    status = "refreshed" if (had_ours and changed) else "installed"
    if changed or force:
        _write_settings(settings_path, data)
    return HookResult(status, rel, primary, primary, SESSION_HOOK_MARKER)


def install_turn_groups(
    repo: Path,
    settings_rel: str,
    specs: tuple[TurnHookSpec, ...],
    runner: str,
    *,
    force: bool = False,
) -> dict[str, HookResult]:
    """Merge the per-turn injection groups into the settings file. Each group runs
    ``{runner} <Event>`` (the envelope entrypoint). Marker-guarded, idempotent, foreign-safe.
    Returns ``{spec.key: HookResult}``; a single ``{"_": malformed}`` when settings is
    unparseable. Sorted by the spec order for deterministic install-state."""
    settings_path = repo / settings_rel
    rel = settings_path.relative_to(repo).as_posix()

    data = _load_settings(settings_path)
    if data is None:
        return {"_": HookResult("malformed", rel, None, None, SESSION_HOOK_MARKER)}

    by_event: dict[str, list[TurnHookSpec]] = {}
    for spec in specs:
        by_event.setdefault(spec.event, []).append(spec)

    changed = False
    results: dict[str, HookResult] = {}
    for event, event_specs in by_event.items():
        existing = (data.get("hooks") or {}).get(event)
        existing = existing if isinstance(existing, list) else []
        had_ours = any(_is_ours(group) for group in existing)
        our_groups = [_group(spec.matcher, [f"{runner} {spec.event}"]) for spec in event_specs]
        event_changed = _merge_codas_groups(data, event, our_groups)
        if event_changed:
            changed = True
        for spec in event_specs:
            command = f"{runner} {spec.event}"
            status = "refreshed" if (had_ours and event_changed) else "installed"
            results[spec.key] = HookResult(status, rel, command, command, SESSION_HOOK_MARKER)
    if changed or force:
        _write_settings(settings_path, data)
    return results
