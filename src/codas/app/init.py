from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_CONFIG = """\
version: 1
mode: bootstrap

project:
  name: my-project
  purpose: Describe what this repository is.

workspace:
  roots:
    - .

constraint_sources:
  authoritative:
    - .codas/config.yml
    - .codas/policies.yml
    - .codas/structure.yml
    - .codas/waivers.yml
  supporting: []

# Configure a workflow adapter (e.g. trellis) + dogfooding.protocol as the project grows.
"""

_POLICIES = """\
version: 1
# Declare governance policies here as you adopt them, e.g.:
#   stale_claim:
#     severity: warning
#     description: Markdown link references must point to existing paths.
policies: {}
"""

_STRUCTURE = """\
version: 1
kind: structure_map
source: .codas/structure.yml
units:
  root:
    path: .
    kind: directory
    owner: maintainers
    purpose: Repository root.
    canonical_placement: Top-level files belong at the repository root.
"""

_WAIVERS = """\
version: 1
# Each waiver must declare reason, owner, scope and expiry.
waivers: []
"""

# Ordered (path, content) so scaffolding is deterministic.
_TEMPLATES: tuple[tuple[str, str], ...] = (
    (".codas/config.yml", _CONFIG),
    (".codas/policies.yml", _POLICIES),
    (".codas/structure.yml", _STRUCTURE),
    (".codas/waivers.yml", _WAIVERS),
)


@dataclass(frozen=True)
class ScaffoldResult:
    written: tuple[str, ...]
    skipped: tuple[str, ...]  # already existed and preserved (no --force)


def scaffold(repo: Path, *, force: bool = False) -> ScaffoldResult:
    """Write a minimal valid ``.codas/`` skeleton — the inverse of ``codas doctor``.

    Creates ``config.yml`` / ``policies.yml`` / ``structure.yml`` / ``waivers.yml`` (the
    doctor-required set), each a loadable template, so a fresh repo passes ``codas
    doctor``. NEVER overwrites an existing file unless ``force`` (so re-running in a
    configured repo can't clobber real config); skipped files are reported. Deterministic
    fixed order; app-layer only, no LLM (§17). The scaffolded ``policies:`` is empty so a
    non-Codas repo's ``policy_registry`` stays 0, and no workflow adapter is declared so
    ``doctor``'s Trellis check is n/a until the user configures one.

    Symlink-safe (this is a setup tool that may run in CI / on an untrusted repo): a
    symlinked ``.codas/`` dir is refused outright (its target could be outside the repo),
    and a symlinked target file — even a DANGLING one, which ``exists()`` misreports as
    absent — is treated as present (skipped without ``force``) and replaced with a real
    file rather than written THROUGH the link when forced.
    """
    written: list[str] = []
    skipped: list[str] = []
    # Never scaffold THROUGH a symlinked .codas dir (it could resolve outside the repo).
    codas_dir_is_symlink = (repo / ".codas").is_symlink()
    for rel, content in _TEMPLATES:
        path = repo / rel
        present = path.exists() or path.is_symlink()  # is_symlink() catches dangling links
        if codas_dir_is_symlink or (present and not force):
            skipped.append(rel)
            continue
        if path.is_symlink():  # force: drop the link, write a real file (don't follow it)
            path.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written.append(rel)
    return ScaffoldResult(tuple(written), tuple(skipped))
