"""The per-turn injection HOOK ENTRYPOINT — agent-neutral.

Invoked as ``codas agent-hook <Event>`` by the rendered per-turn hooks of any supported agent
(Claude Code's ``.claude/settings.json``, Codex CLI's ``.codex/hooks.json``). It reads the repo
from the hook input (stdin ``cwd``, else the process cwd), computes the advisory changed-file
context (``app.status.inject_context`` — neutral, deduped, capped, NEVER-raising), and prints
the ``additionalContext`` envelope so the finding reaches the MAIN agent:

    {"hookSpecificOutput": {"hookEventName": "<Event>", "additionalContext": "<text>"}}

Both Claude Code and Codex CLI consume this exact envelope shape. Prints NOTHING (exit 0) when
there is nothing to surface, so a clean turn injects nothing. Why an entrypoint and not a flag
on ``codas status``: the envelope is the platform integration's concern, so it lives in
``integrations`` (the platform shim) while ``codas status`` stays neutral (§11/§17).
``integrations`` may import ``app`` (the permitted direction); the CLI may not import this.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from codas.app.status import inject_context

# Events that inject advisory context. ``hookEventName`` in the envelope must match the firing
# event (the host validates it). SessionStart is NOT here — the session BASELINE is recorded by
# the neutral ``codas status --record-baseline`` chained into that hook, and the digest rides
# the chained ``codas preflight`` stdout. ``UserPromptSubmit`` is the primary Codex per-turn
# carrier (the documented context-injection event there); it is harmless for Claude.
_INJECTING_EVENTS = ("Stop", "SubagentStop", "PostToolUse", "UserPromptSubmit")


def _repo_from_stdin() -> Path | None:
    """The repo root from the hook input JSON on stdin (its ``cwd`` field). ``None`` when
    stdin is a tty / empty / unparseable — the caller falls back to the process cwd."""
    try:
        if sys.stdin.isatty():
            return None
        raw = sys.stdin.read()
        if not raw.strip():
            return None
        data = json.loads(raw)
        cwd = data.get("cwd") if isinstance(data, dict) else None
        return Path(cwd) if isinstance(cwd, str) and cwd else None
    except Exception:  # noqa: BLE001 — a hook must never crash the turn it advises.
        return None


def run_agent_hook(argv: list[str] | None = None) -> int:
    """Emit the additionalContext envelope for an injecting event; nothing otherwise. A unique
    top-level name (NOT ``main``) so it never collides with the CLI entrypoint under
    duplicate_implementation (S10)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    event = argv[0] if argv else "Stop"
    try:
        repo = _repo_from_stdin() or Path.cwd()
        text = inject_context(repo)
        if text and event in _INJECTING_EVENTS:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": event,
                            "additionalContext": text,
                        }
                    }
                )
            )
    except Exception:  # noqa: BLE001 — never block the turn; exit 0, inject nothing.
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_agent_hook())
