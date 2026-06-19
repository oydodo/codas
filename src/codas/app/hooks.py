from __future__ import annotations

from pathlib import Path

from codas.integrations.enforcement import (
    DEFAULT_CHECK_COMMAND,
    InstallResult,
    install_hooks,
)


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
