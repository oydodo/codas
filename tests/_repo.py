"""Golden-repo builder for the whole-product acceptance suite.

A ``GoldenRepo`` is a synthetic, valid, git-committed Codas repo that ``run_check`` returns
ZERO findings for. Acceptance cases build one and apply ONE mutation, so a finding is
attributable to that mutation. See
``.trellis/tasks/06-22-acceptance-golden-repo/prd.md`` and the charter design at
``.trellis/tasks/archive/2026-06/06-22-acceptance-suite/design.md``.

Design folds honoured here (from the charter DESIGN review):
- B3: the ``check`` profile has NO ``.`` repo-root catch-all unit (it would own every file and
  make ``missing_structure_owner`` untriggerable). A single ``.codas`` unit owns the whole
  governance tree, and the golden keeps every file under ``.codas`` so nothing is left unowned.
- B1: ``policy_registry`` scans the TARGET repo's ``src/codas/policies/`` tree. The golden ships
  no such tree AND declares ``policies: {}``, so implemented == declared == empty → clean. The
  policy-registry / severity-catalog cases run against the REAL repo, not the golden (charter Q1).
- Profiles (charter Q2): ``check`` is the minimal gate-clean repo. Add ``wiki``/``agent``/``full``
  later by extending ``_PROFILES`` — no refactor needed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import codas
from codas.app.check import run_check
from codas.core.models import CheckReport

# The src/ dir the installed codas package lives under — passed to subprocess CLI runs so a
# `python -m codas` against the golden uses THIS checkout, not a globally-installed one.
_SRC_DIR = str(Path(codas.__file__).resolve().parents[1])


@dataclass
class GoldenRepo:
    """A handle to a built golden repo on disk."""

    root: Path
    _committed: bool = field(default=False, repr=False)

    def write(self, relpath: str, content: str) -> Path:
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def remove(self, relpath: str) -> None:
        (self.root / relpath).unlink(missing_ok=True)

    def commit(self, msg: str = "seed") -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", msg)
        self._committed = True

    def check(self) -> CheckReport:
        """In-process full gate over the golden (the real public entry point)."""
        return run_check(self.root)

    def kinds(self) -> set[tuple[str, str]]:
        """``{(check_id, severity)}`` — convenience for asserting which findings fired."""
        return {(f.check_id, f.severity) for f in self.check().findings}

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        """Drive the REAL ``python -m codas`` subprocess (the wiring surface, M9)."""
        env = {**os.environ, "PYTHONPATH": _SRC_DIR}
        return subprocess.run(
            [sys.executable, "-m", "codas", *args],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "golden",
            "GIT_AUTHOR_EMAIL": "golden@example.invalid",
            "GIT_COMMITTER_NAME": "golden",
            "GIT_COMMITTER_EMAIL": "golden@example.invalid",
        },
    )


# --- profile content -------------------------------------------------------------------

_CONFIG_YML = """\
version: 1
mode: bootstrap

project:
  name: Golden
  purpose: Acceptance-suite golden fixture.

workspace:
  roots:
    - .

dogfooding:
  enabled: true
  protocol: .codas/config.yml

workflow:
  adapter: none

wiki:
  enabled: false
"""

_POLICIES_YML = """\
version: 1
mode: bootstrap
policies: {}
"""

_STRUCTURE_YML = """\
version: 1
kind: structure_map

units:
  codas-config:
    path: .codas
    kind: governance_state
    owner: Golden Owner
    purpose: Codas governance state.
    canonical_placement: Governance files live under .codas.
"""

_PROGRAM_YML = """\
version: 1
kind: program_plan

metadata:
  project: Golden
  owner: Golden Owner
  summary: Golden fixture program plan.

work_items:
  - id: program:P0:golden-baseline
    phase: P0
    title: Golden baseline
    status: completed
    depends_on: []
    deliverables: []
    exit_criteria: []
"""

_WAIVERS_YML = """\
version: 1
waivers: []
"""

_CLAIMS_YML = """\
version: 1
"""

# A profile = the {relpath: content} a build lays down. ``check`` = the minimal gate-clean repo.
_PROFILES: dict[str, dict[str, str]] = {
    "check": {
        ".codas/config.yml": _CONFIG_YML,
        ".codas/policies.yml": _POLICIES_YML,
        ".codas/structure.yml": _STRUCTURE_YML,
        ".codas/program.yml": _PROGRAM_YML,
        ".codas/waivers.yml": _WAIVERS_YML,
        ".codas/claims.yml": _CLAIMS_YML,
    },
}


def build_golden(tmp: Path, *, profile: str = "check", commit: bool = True) -> GoldenRepo:
    """Build a valid, zero-finding, git-committed golden repo under ``tmp``.

    ``tmp`` should be an empty directory (e.g. a ``TemporaryDirectory``). ``commit=False``
    skips the initial commit (for tests that want an uncommitted working tree)."""
    files = _PROFILES.get(profile)
    if files is None:
        raise ValueError(f"unknown golden profile: {profile!r}")
    repo = GoldenRepo(root=tmp)
    _git(tmp, "init", "-q")
    for relpath, content in files.items():
        repo.write(relpath, content)
    if commit:
        repo.commit("golden seed")
    return repo
