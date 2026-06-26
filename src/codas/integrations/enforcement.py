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

    The command runs as the script's LAST line (no ``exec``): the hook then exits with the
    command's status, blocking the git op on a non-zero ``codas check``. ``exec`` is avoided
    deliberately — ``exec VAR=val cmd`` is invalid in sh (exec cannot take an env-var prefix),
    so a source-checkout command like ``PYTHONPATH=src python3 -m codas check .`` would fail
    with 'exec: PYTHONPATH=src: not found'; a plain line lets sh parse the assignment.
    """
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER} ({hook_name})\n"
        "# Installed by `codas hooks --install`. Blocks the operation when\n"
        "# `codas check` reports error findings. Remove this file to disable.\n"
        f"{command}\n"
    )


def render_workflow() -> str:
    """Render the committed GitHub Action CI gate (`.github/workflows/codas.yml`).

    Runs the bootstrap test gate + ``codas check`` + the freshness ``--verify``s on
    push / pull_request so a bad change OR a stale generated doc (the AGENTS.md governance
    block, the wiki book) fails CI. The ``--verify`` steps are the BINDING staleness gate
    (``codas doctor`` only WARNS on staleness; CI is what fails). Installs the
    package from the checkout so CI verifies both the console script entry point and
    the repository gate. Deterministic, no timestamp.
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
        "        run: python -m pip install -e .\n"
        "      - name: Bootstrap tests\n"
        "        run: python -m unittest discover -s tests\n"
        "      - name: Codas check\n"
        "        run: codas check .\n"
        "      - name: Codas agents verify\n"
        "        run: codas agents --verify .\n"
        "      - name: Codas wiki verify\n"
        "        run: codas wiki --verify .\n"
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


def git_hook_status(repo: Path) -> dict[str, str]:
    """Live state of each git hook: ``{name: installed | foreign | absent}`` (ground truth).

    Reads the ACTUAL hook files (honoring ``core.hooksPath`` via ``_hooks_dir``), so a reader like
    ``codas doctor`` sees reality — not just what an installer once recorded in
    ``.install-state.json`` (which can be stale if a user removed a hook post-install). A non-git
    repo or no usable hooks dir → every hook ``absent``. Pure read-only; reuses the same marker
    check the installer uses so detection cannot fork from installation.
    """
    hooks_dir = _hooks_dir(repo)
    if hooks_dir is None:
        return {name: "absent" for name in HOOK_NAMES}
    status: dict[str, str] = {}
    for name in HOOK_NAMES:
        path = hooks_dir / name
        if not path.exists():
            status[name] = "absent"
        elif _is_codas_hook(path.read_text(errors="ignore")):
            status[name] = "installed"
        else:
            status[name] = "foreign"
    return status


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
