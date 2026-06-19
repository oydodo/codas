from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.adapters.git import extract_changed_paths
from codas.config.loader import CodasConfig
from codas.facts.context import ScanContext
from codas.policies.spec_drift import check_spec_drift


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", "main")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")


def _ctx(repo: Path, changed: tuple[str, ...]) -> ScanContext:
    config = CodasConfig(path=repo / ".codas" / "config.yml", raw={})
    ctx = ScanContext(repo=repo, config=config, roots=(), files=())
    ctx._cache["changed_paths"] = tuple(sorted(changed))
    return ctx


def _write_claims(repo: Path, body: str) -> None:
    (repo / ".codas").mkdir(parents=True, exist_ok=True)
    (repo / ".codas" / "claims.yml").write_text(body)


class ExtractChangedPathsTests(unittest.TestCase):
    def test_clean_tree_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _init_repo(repo)
            self.assertEqual(extract_changed_paths(repo), ())

    def test_modify_add_delete_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _init_repo(repo)
            (repo / "seed.txt").write_text("seed changed\n")  # tracked modify
            (repo / "new.txt").write_text("new\n")            # untracked add
            (repo / "gone.txt").write_text("x\n")
            _git(repo, "add", "gone.txt")
            _git(repo, "commit", "-q", "-m", "add gone")
            (repo / "gone.txt").unlink()                      # tracked delete
            got = extract_changed_paths(repo)
            self.assertEqual(got, ("gone.txt", "new.txt", "seed.txt"))

    def test_path_with_space_survives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _init_repo(repo)
            (repo / "a b.txt").write_text("spaced\n")  # untracked, NUL-parsed
            self.assertIn("a b.txt", extract_changed_paths(repo))

    def test_non_git_directory_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(extract_changed_paths(Path(directory)), ())


_COUPLING = """\
version: 1
kind: claim_set
drift_couplings:
  - when_changed: src/codas/foo.py
    requires:
      - docs/foo.md
    owner: Codas Core
    reason: foo behavior is documented in docs/foo.md.
"""


class CheckSpecDriftTests(unittest.TestCase):
    def test_unmet_requirement_is_a_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(repo, _COUPLING)
            ctx = _ctx(repo, ("src/codas/foo.py",))  # site changed, doc not
            findings = check_spec_drift(ctx)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].check_id, "spec-drift")
            self.assertEqual(findings[0].severity, "error")
            self.assertEqual(findings[0].meta["when_changed"], "src/codas/foo.py")
            self.assertEqual(findings[0].meta["requires"], "docs/foo.md")

    def test_requirement_met_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(repo, _COUPLING)
            ctx = _ctx(repo, ("src/codas/foo.py", "docs/foo.md"))
            self.assertEqual(check_spec_drift(ctx), [])

    def test_dormant_when_site_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(repo, _COUPLING)
            ctx = _ctx(repo, ("src/codas/other.py",))  # site not in diff
            self.assertEqual(check_spec_drift(ctx), [])

    def test_clean_tree_short_circuits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(repo, _COUPLING)
            ctx = _ctx(repo, ())  # empty diff -> no drift even with couplings
            self.assertEqual(check_spec_drift(ctx), [])

    def test_glob_when_and_requires(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(
                repo,
                "version: 1\nkind: claim_set\ndrift_couplings:\n"
                "  - when_changed: src/codas/policies/**\n"
                "    requires:\n      - docs/policies/*.md\n",
            )
            site = _ctx(repo, ("src/codas/policies/spec_drift.py",))
            self.assertEqual(len(check_spec_drift(site)), 1)  # glob site, no doc
            met = _ctx(
                repo,
                ("src/codas/policies/spec_drift.py", "docs/policies/spec_drift.md"),
            )
            self.assertEqual(check_spec_drift(met), [])

    def test_no_drift_couplings_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(repo, "version: 1\nkind: claim_set\n")
            ctx = _ctx(repo, ("src/codas/foo.py",))
            self.assertEqual(check_spec_drift(ctx), [])

    def test_missing_claims_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            ctx = _ctx(repo, ("src/codas/foo.py",))
            self.assertEqual(check_spec_drift(ctx), [])

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_claims(repo, _COUPLING)
            ctx = _ctx(repo, ("src/codas/foo.py",))
            self.assertEqual(check_spec_drift(ctx), check_spec_drift(ctx))


if __name__ == "__main__":
    unittest.main()
