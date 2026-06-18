from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.policies.duplicate_symbol import check_duplicate_symbol


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class DuplicateSymbolPolicyTests(unittest.TestCase):
    def test_public_function_repeated_across_src_modules_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")

            findings = check_duplicate_symbol(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            finding = findings[0]
            self.assertEqual(finding.check_id, "duplicate-symbol")
            self.assertEqual(finding.severity, "warning")
            self.assertEqual(finding.meta["name"], "handle")
            self.assertEqual(finding.meta["modules"], ["src/a.py", "src/b.py"])
            self.assertEqual(
                [(e.path, e.line) for e in finding.evidence],
                [("src/a.py", 1), ("src/b.py", 1)],
            )

    def test_public_class_repeated_is_flagged_with_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "class Widget:\n    pass\n")
            _write(repo / "src" / "pkg" / "b.py", "class Widget:\n    pass\n")

            findings = check_duplicate_symbol(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].meta["name"], "Widget")
            self.assertEqual(findings[0].evidence[0].detail, "class")

    def test_private_duplicates_are_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def _rel():\n    pass\n")
            _write(repo / "src" / "b.py", "def _rel():\n    pass\n")

            self.assertEqual(check_duplicate_symbol(repo, _config(repo)), [])

    def test_single_definition_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def only():\n    pass\n")

            self.assertEqual(check_duplicate_symbol(repo, _config(repo)), [])

    def test_test_helpers_are_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "tests" / "x.py", "def helper():\n    pass\n")
            _write(repo / "tests" / "y.py", "def helper():\n    pass\n")

            self.assertEqual(check_duplicate_symbol(repo, _config(repo)), [])

    def test_vendored_trellis_scripts_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".trellis" / "scripts" / "a.py", "def go():\n    pass\n")
            _write(repo / ".trellis" / "scripts" / "b.py", "def go():\n    pass\n")

            self.assertEqual(check_duplicate_symbol(repo, _config(repo)), [])

    def test_cross_kind_same_name_groups_into_one_finding(self) -> None:
        # class Foo in one module + def Foo in another → one duplicate-symbol
        # finding (grouped by name; kind carried per-evidence). Codex review #5.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "class Foo:\n    pass\n")
            _write(repo / "src" / "b.py", "def Foo():\n    pass\n")

            findings = check_duplicate_symbol(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            self.assertEqual(
                [e.detail for e in findings[0].evidence], ["class", "function"]
            )

    def test_reexport_does_not_inflate_module_count(self) -> None:
        # A re-export is an ImportFrom node, not a def, so the adapter never emits
        # it as a symbol → the name stays single-module and is not flagged.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def Thing():\n    pass\n")
            _write(repo / "src" / "pkg.py", "from .a import Thing\n")

            self.assertEqual(check_duplicate_symbol(repo, _config(repo)), [])

    def test_same_name_twice_in_one_module_is_not_cross_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def dup():\n    pass\n\n\ndef dup():\n    pass\n")

            self.assertEqual(check_duplicate_symbol(repo, _config(repo)), [])

    def test_findings_sorted_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def zeta():\n    pass\n\n\ndef alpha():\n    pass\n")
            _write(repo / "src" / "b.py", "def zeta():\n    pass\n\n\ndef alpha():\n    pass\n")

            findings = check_duplicate_symbol(repo, _config(repo))

            self.assertEqual([f.meta["name"] for f in findings], ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
