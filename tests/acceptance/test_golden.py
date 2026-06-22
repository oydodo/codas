"""Acceptance — the golden-repo harness itself (step 1 of the whole-product suite).

Proves the foundation every later acceptance case rests on: ``build_golden`` produces a
genuinely clean synthetic repo through the REAL ``run_check`` and the REAL ``python -m codas``
CLI. If this drifts (a new gated policy the golden does not satisfy), the whole suite must be
revisited — which is the point.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from _repo import build_golden


class GoldenRepoTests(unittest.TestCase):
    def test_golden_is_clean_in_process(self) -> None:
        """The keystone: a synthetic golden has ZERO findings through run_check."""
        with tempfile.TemporaryDirectory() as d:
            report = build_golden(Path(d)).check()
            self.assertEqual(
                report.findings,
                [],
                msg="golden is not clean: "
                + "; ".join(f"[{f.severity}] {f.check_id}: {f.message}" for f in report.findings),
            )

    def test_golden_cli_check_exits_zero(self) -> None:
        """The real entry point an agent/CI uses agrees with the in-process check."""
        with tempfile.TemporaryDirectory() as d:
            result = build_golden(Path(d)).cli("check", ".")
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_golden_working_tree_clean_after_commit(self) -> None:
        """commit() leaves a clean tree — required for the fact_coupling (diff-based) case."""
        with tempfile.TemporaryDirectory() as d:
            build_golden(Path(d))  # commits by default
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=d, capture_output=True, text=True
            ).stdout
            self.assertEqual(status.strip(), "")

    def test_uncommitted_profile_leaves_files_staged_for_working_tree_cases(self) -> None:
        """commit=False keeps the seed in the working tree (a case can then mutate + diff)."""
        with tempfile.TemporaryDirectory() as d:
            build_golden(Path(d), commit=False)
            self.assertTrue((Path(d) / ".codas" / "config.yml").exists())

    def test_unknown_profile_raises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                build_golden(Path(d), profile="does-not-exist")

    def test_golden_is_not_vacuously_clean(self) -> None:
        """Negative control: a known violation MUST surface. Proves run_check actually
        exercises policies on the golden (a clean result is real, not a swallowed error).
        Adds a file under a governed path that no unit owns → missing-structure-owner."""
        with tempfile.TemporaryDirectory() as d:
            golden = build_golden(Path(d))
            golden.write("src/orphan.py", "x = 1\n")  # no unit owns src/ in the golden
            kinds = golden.kinds()
            self.assertIn(
                ("missing-structure-owner", "error"),
                kinds,
                msg=f"expected an unowned-file finding; got {sorted(kinds)}",
            )


if __name__ == "__main__":
    unittest.main()
