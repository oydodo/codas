from __future__ import annotations

import json
from pathlib import Path

# The machine-local install-state marker: the doctor<->installer contract (the 1/4 reader
# consumes what these installers write). MUST stay out of the byte-identical inventory — it is
# gitignored AND in structure.index._IGNORE_PATHS (the injection-MVP BLOCKER#1), so a fresh
# write never moves the inventory hash. Each installer MERGES its own top-level key, so the git
# installer and the agent installer update independent slices without clobbering each other.
INSTALL_STATE_PATH = ".codas/.install-state.json"
SCHEMA_VERSION = 1


def hook_state(
    status: str,
    *,
    expected_command: str | None = None,
    installed_command: str | None = None,
    settings_path: str | None = None,
    marker_id: str | None = None,
    trusted: str | None = None,
) -> dict:
    """One hook's state for the contract. ``status`` ∈ installed | refreshed | stale | foreign
    | skipped | absent | malformed. ``trusted`` carries the Claude workspace-trust state
    (true/false/unknown) for agent hooks; ``None`` for git hooks (no trust concept)."""
    return {
        "status": status,
        "expected_command": expected_command,
        "installed_command": installed_command,
        "settings_path": settings_path,
        "marker_id": marker_id,
        "trusted": trusted,
    }


def read_install_state(repo: Path) -> dict:
    """The current install-state (``{}`` if absent or malformed). Consumed by the 1/4 doctor
    reader; tolerant by design so a hand-corrupted marker never hard-fails a diagnostic."""
    path = repo / INSTALL_STATE_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def merge_install_state(repo: Path, updates: dict) -> Path:
    """Read-merge-write the install-state: set ``schema_version`` and overlay each top-level key
    in ``updates`` (e.g. ``git_hooks``, ``agent_hooks``, ``agents_block``, ``claude_shim``),
    preserving keys other installers own. Deterministic bytes (sorted, trailing newline) so the
    marker diffs cleanly; it is gitignored, so determinism is for tooling, not the hash."""
    data = read_install_state(repo)
    data["schema_version"] = SCHEMA_VERSION
    data.update(updates)
    path = repo / INSTALL_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
