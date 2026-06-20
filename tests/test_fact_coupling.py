"""spec-drift v2-B: fact-level co-change couplings (check_fact_coupling).

The gating half of spec-drift v2: a coupling watches a working-tree-vs-HEAD fact delta
(symbol/import/call added/removed) and requires a companion path to co-change in the same
diff. Always-true by construction (a comment fix produces no delta -> dormant); a
malformed coupling is an error, not a silent skip. The live repo coupling
("a new check_* under src/codas/policies requires src/codas/app/check.py to co-change")
is exercised against fixtures here.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.adapters.git import extract_changed_paths
from codas.config.loader import CodasConfig
from codas.facts.context import build_scan_context
from codas.policies.fact_coupling import check_fact_coupling


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


_COUPLING = """\
version: 1
kind: claim_set
fact_couplings:
  - when_fact:
      kind: symbol_added
      scope: pkg/policies
      name: "check_*"
    requires:
      - pkg/app.py
    owner: T
    reason: a new check_* must be wired into app
"""


def _scaffold(repo: Path, claims: str = _COUPLING) -> None:
    _init(repo)
    _write(repo / ".codas" / "claims.yml", claims)
    _write(repo / "pkg" / "__init__.py", "")
    _write(repo / "pkg" / "policies" / "__init__.py", "")
    _write(repo / "pkg" / "policies" / "p.py", "def check_existing(ctx):\n    return []\n")
    _write(repo / "pkg" / "app.py", "def run():\n    pass\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")


def _claims(kind: str = "symbol_added", scope: str = "pkg/policies",
            name: str = '"check_*"', requires=("pkg/app.py",)) -> str:
    name_line = f"      name: {name}\n" if name else ""
    req_lines = "".join(f"      - {r}\n" for r in requires)
    return (
        "version: 1\nkind: claim_set\nfact_couplings:\n"
        f"  - when_fact:\n      kind: {kind}\n      scope: {scope}\n{name_line}"
        f"    requires:\n{req_lines}    owner: T\n    reason: t\n"
    )


def _findings(repo: Path):
    return check_fact_coupling(build_scan_context(repo, _config(repo)))


class CleanTreeTests(unittest.TestCase):
    def test_clean_tree_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo)
            self.assertEqual(_findings(repo), [])  # HEAD == working -> empty delta

    def test_no_claims_file_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _write(repo / "pkg" / "__init__.py", "")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "base")
            self.assertEqual(_findings(repo), [])


class TeethTests(unittest.TestCase):
    def test_added_check_without_companion_fires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo)
            # add a check_* under the scope, do NOT touch the required companion
            _write(
                repo / "pkg" / "policies" / "p.py",
                "def check_existing(ctx):\n    return []\n\n\ndef check_new(ctx):\n    return []\n",
            )
            findings = _findings(repo)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].check_id, "fact-coupling")
            self.assertIn("pkg/app.py", findings[0].message)

    def test_added_check_with_companion_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo)
            _write(
                repo / "pkg" / "policies" / "p.py",
                "def check_existing(ctx):\n    return []\n\n\ndef check_new(ctx):\n    return []\n",
            )
            _write(repo / "pkg" / "app.py", "def run():\n    pass\n# wired check_new\n")
            self.assertEqual(_findings(repo), [])  # companion co-changed -> satisfied

    def test_non_matching_name_does_not_fire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo)
            # a new symbol under scope but NOT check_* -> name filter excludes it
            _write(
                repo / "pkg" / "policies" / "p.py",
                "def check_existing(ctx):\n    return []\n\n\ndef helper():\n    pass\n",
            )
            self.assertEqual(_findings(repo), [])

    def test_out_of_scope_addition_does_not_fire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo)
            # a check_* added OUTSIDE the coupling scope -> no match
            _write(repo / "pkg" / "other.py", "def check_elsewhere(ctx):\n    return []\n")
            self.assertEqual(_findings(repo), [])


class MalformedTests(unittest.TestCase):
    def _malformed(self, claims: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo, claims=claims)
            findings = _findings(repo)
            self.assertTrue(findings, "expected a malformed-coupling error")
            self.assertTrue(all(f.check_id == "fact-coupling" for f in findings))
            self.assertTrue(all("Malformed" in f.message for f in findings))

    def test_fact_couplings_not_a_list(self) -> None:
        self._malformed("version: 1\nkind: claim_set\nfact_couplings: nope\n")

    def test_entry_missing_kind(self) -> None:
        self._malformed(
            "version: 1\nkind: claim_set\n"
            "fact_couplings:\n  - when_fact:\n      scope: pkg\n    requires: [pkg/a.py]\n"
        )

    def test_entry_bad_kind(self) -> None:
        self._malformed(
            "version: 1\nkind: claim_set\n"
            "fact_couplings:\n  - when_fact:\n      kind: file_changed\n      scope: pkg\n"
            "    requires: [pkg/a.py]\n"
        )

    def test_entry_empty_requires(self) -> None:
        self._malformed(
            "version: 1\nkind: claim_set\n"
            "fact_couplings:\n  - when_fact:\n      kind: symbol_added\n      scope: pkg\n"
            "    requires: []\n"
        )

    def test_empty_name_is_malformed(self) -> None:
        # an empty `name` would fnmatch nothing -> silently disable the gate (codex NIT)
        self._malformed(_claims(name='""'))


class KindStreamTests(unittest.TestCase):
    """The other delta streams beyond symbol_added (codex SHOULD-3 coverage gap)."""

    def test_import_added_kind_fires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo, claims=_claims(kind="import_added", scope="pkg", name=""))
            _write(repo / "pkg" / "policies" / "p.py", "import os\n\n\ndef check_existing(ctx):\n    return []\n")
            findings = _findings(repo)
            self.assertEqual(len(findings), 1)
            self.assertIn("import_added", findings[0].message)

    def test_symbol_removed_kind_fires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo, claims=_claims(kind="symbol_removed"))
            # remove check_existing without touching the companion
            _write(repo / "pkg" / "policies" / "p.py", "def kept(ctx):\n    return []\n")
            findings = _findings(repo)
            self.assertEqual(len(findings), 1)
            self.assertIn("symbol_removed", findings[0].message)


class NormalizationAndOrderTests(unittest.TestCase):
    def test_requires_path_is_normalized(self) -> None:
        # requires "./pkg/app.py" must match changed_paths "pkg/app.py" (codex NIT)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo, claims=_claims(requires=("./pkg/app.py",)))
            _write(
                repo / "pkg" / "policies" / "p.py",
                "def check_existing(ctx):\n    return []\n\n\ndef check_new(ctx):\n    return []\n",
            )
            _write(repo / "pkg" / "app.py", "def run():\n    pass\n# wired\n")
            self.assertEqual(_findings(repo), [])  # normalized companion satisfies

    def test_multiple_missing_requires_are_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _scaffold(repo, claims=_claims(requires=("pkg/z.py", "pkg/app.py")))
            _write(
                repo / "pkg" / "policies" / "p.py",
                "def check_existing(ctx):\n    return []\n\n\ndef check_new(ctx):\n    return []\n",
            )
            findings = _findings(repo)
            self.assertEqual(len(findings), 2)
            reqs = [f.meta["requires"] for f in findings]
            self.assertEqual(reqs, sorted(reqs))  # deterministic order


class ChangedPathsTests(unittest.TestCase):
    """extract_changed_paths edge cases (restored from the deleted spec_drift suite)."""

    def test_non_git_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(extract_changed_paths(Path(tmp)), ())

    def test_modify_add_delete_all_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _write(repo / "a.py", "x = 1\n")
            _write(repo / "b.py", "y = 2\n")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "base")
            _write(repo / "a.py", "x = 99\n")          # modify tracked
            (repo / "b.py").unlink()                    # delete tracked
            _write(repo / "c.py", "z = 3\n")            # add untracked
            changed = extract_changed_paths(repo)
            self.assertEqual(changed, tuple(sorted(("a.py", "b.py", "c.py"))))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
