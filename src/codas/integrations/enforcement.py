from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .install_state import hook_state, merge_install_state

# Hook bodies carry this marker so the installer recognises (and may refresh) its own
# hooks and refuses to trample a foreign hook the user already wrote.
HOOK_MARKER = "# codas-managed-hook"
HOOK_NAMES = ("pre-commit", "pre-push")
DEFAULT_CHECK_COMMAND = "codas check ."


@dataclass(frozen=True)
class InstallResult:
    """Outcome of ``install_hooks``: hook names written vs left untouched."""

    hooks_dir: str
    installed: tuple[str, ...]
    skipped: tuple[str, ...]  # foreign (non-Codas) hooks preserved


def render_hook(hook_name: str, command: str = DEFAULT_CHECK_COMMAND) -> str:
    """Render a POSIX-sh git hook body that gates on ``codas check`` (pure).

    Deterministic — byte-identical across calls for the same args, so a re-install of
    an unchanged hook is a no-op write.
    """
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER} ({hook_name})\n"
        "# Installed by `codas hooks --install`. Blocks the operation when\n"
        "# `codas check` reports error findings. Remove this file to disable.\n"
        f"exec {command}\n"
    )


def render_workflow() -> str:
    """Render the committed GitHub Action CI gate (`.github/workflows/codas.yml`).

    Runs the bootstrap test gate + ``codas check`` on push / pull_request so a bad
    change fails CI. Uses the repo's ``PYTHONPATH=src`` form (Codas is not yet a
    published package); a packaged install would shorten this to ``codas check .``.
    Deterministic, no timestamp.
    """
    return (
        "name: codas\n"
        "on:\n"
        "  push:\n"
        "  pull_request:\n"
        "jobs:\n"
        "  check:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        '          python-version: "3.11"\n'
        "      - name: Install dependencies\n"
        "        run: python -m pip install pyyaml\n"
        "      - name: Bootstrap tests\n"
        "        run: PYTHONPATH=src python -m unittest discover -s tests\n"
        "      - name: Codas check\n"
        "        run: PYTHONPATH=src python -m codas check .\n"
    )


def install_hooks(
    repo: Path, *, force: bool = False, command: str = DEFAULT_CHECK_COMMAND
) -> InstallResult | None:
    """Install ``pre-commit`` / ``pre-push`` hooks that run ``codas check``.

    Writes into the repo's git hooks dir (honouring ``core.hooksPath``, else
    ``.git/hooks``); returns ``None`` if ``repo`` is not a git repository. A hook that
    already exists and is NOT Codas-marked is left untouched unless ``force`` (never
    trample a user's own hook); a Codas-marked hook is refreshed idempotently.
    """
    hooks_dir = _hooks_dir(repo)
    if hooks_dir is None:
        return None
    hooks_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    skipped: list[str] = []
    for name in HOOK_NAMES:
        path = hooks_dir / name
        body = render_hook(name, command)
        if path.exists() and not force:
            existing = path.read_text(errors="ignore")
            if not _is_codas_hook(existing):
                skipped.append(name)  # preserve a foreign hook
                continue
            if existing == body and os.access(path, os.X_OK):
                installed.append(name)  # already current -> no churn (no rewrite/chmod)
                continue
        path.write_text(body)
        path.chmod(0o755)
        installed.append(name)
    result = InstallResult(str(hooks_dir), tuple(installed), tuple(skipped))
    _write_git_hook_state(repo, hooks_dir, installed, command)
    return result


def _write_git_hook_state(
    repo: Path, hooks_dir: Path, installed: list[str], command: str
) -> None:
    """Emit the ``git_hooks`` slice of ``.codas/.install-state.json`` (must-hold #6: the schema
    must not carry state no installer writes). Guarded to a Codas repo (a ``.codas`` dir) so a
    bare repo getting only git hooks is never surprised with a Codas marker file. Per hook:
    ``installed`` (ours, current) vs ``foreign`` (a user hook preserved untouched)."""
    if not (repo / ".codas").is_dir():
        return
    git_hooks = {}
    for name in HOOK_NAMES:
        is_ours = name in installed
        git_hooks[name.replace("-", "_")] = hook_state(
            "installed" if is_ours else "foreign",
            expected_command=command,
            installed_command=command if is_ours else None,
            settings_path=str(hooks_dir / name),
            marker_id=HOOK_MARKER,
        )
    merge_install_state(repo, {"git_hooks": git_hooks})


def _is_codas_hook(text: str) -> bool:
    """True iff a hook is one Codas installed — the marker must sit on line 2 exactly
    where ``render_hook`` puts it, so a foreign hook merely mentioning the marker in an
    unrelated comment is NOT mistaken for ours (and never clobbered without --force)."""
    lines = text.splitlines()
    return len(lines) >= 2 and lines[1].startswith(HOOK_MARKER)


def _hooks_dir(repo: Path) -> Path | None:
    """The repo's git hooks dir (honours ``core.hooksPath``); ``None`` if not usable.

    Returns ``None`` for a non-git repo (or git absent), a bare repo (no worktree), or a
    file-valued ``core.hooksPath`` (e.g. ``/dev/null`` to disable hooks) — so the caller
    fails cleanly instead of crashing on ``mkdir``. A RELATIVE ``core.hooksPath`` is
    resolved against the worktree ROOT (where Git itself resolves it), not the
    invocation directory.
    """
    toplevel = _worktree_root(repo)
    if toplevel is None:
        return None

    configured = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
    )
    if configured.returncode == 0 and configured.stdout.strip():
        path = Path(configured.stdout.strip())
        hooks = path if path.is_absolute() else toplevel / path
    else:
        resolved = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
        )
        candidate = resolved.stdout.strip()
        if resolved.returncode != 0 or not candidate:
            return None
        path = Path(candidate)
        hooks = path if path.is_absolute() else repo / path

    if hooks.exists() and not hooks.is_dir():  # file-valued hooksPath -> not installable
        return None
    return hooks


def _worktree_root(repo: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    top = result.stdout.strip()
    return Path(top) if top else None
