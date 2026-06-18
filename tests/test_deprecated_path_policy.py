from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.policies.deprecated_path import check_deprecated_path_used

STRUCTURE = """\
version: 1
kind: structure_map
units:
  root:
    path: .
    kind: package
    owner: Core
    purpose: x
    canonical_placement: x
deprecated_paths:
  old-pkg:
    path: src/old
    replacement: src/new
    status: removed
    reason: moved to src/new
"""

STRUCTURE_OVERLAPPING = """\
version: 1
kind: structure_map
units:
  root:
    path: .
    kind: package
    owner: Core
    purpose: x
    canonical_placement: x
deprecated_paths:
  old-pkg:
    path: src/old
    replacement: src/new
    status: removed
  old-sub:
    path: src/old/sub
    replacement: src/newer
    status: removed
"""

STRUCTURE_NO_REPLACEMENT = """\
version: 1
kind: structure_map
units:
  root:
    path: .
    kind: package
    owner: Core
    purpose: x
    canonical_placement: x
deprecated_paths:
  old-pkg:
    path: src/old
    status: deprecated
"""


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class DeprecatedPathPolicyTests(unittest.TestCase):
    def test_file_under_deprecated_prefix_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", STRUCTURE)
            _write(repo / "src" / "old" / "legacy.py")

            findings = check_deprecated_path_used(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            finding = findings[0]
            self.assertEqual(finding.check_id, "deprecated-path-used")
            self.assertEqual(finding.severity, "error")
            self.assertEqual(finding.evidence[0].path, "src/old/legacy.py")
            self.assertEqual(finding.evidence[1].path, ".codas/structure.yml")
            self.assertIn("src/new", finding.recommendation)
            self.assertIn("moved to src/new", finding.recommendation)
            self.assertEqual(finding.meta["replacement"], "src/new")
            self.assertEqual(finding.meta["status"], "removed")

    def test_prefix_boundary_sibling_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", STRUCTURE)
            _write(repo / "src" / "older.py")  # shares the literal prefix, different path

            self.assertEqual(check_deprecated_path_used(repo, _config(repo)), [])

    def test_deprecated_path_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", STRUCTURE_NO_REPLACEMENT)
            _write(repo / "src" / "old" / "legacy.py")

            findings = check_deprecated_path_used(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            self.assertEqual(
                findings[0].recommendation, "Move it out of the deprecated path."
            )
            self.assertIn("deprecated", findings[0].message)

    def test_overlapping_prefixes_report_once_most_specific(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", STRUCTURE_OVERLAPPING)
            _write(repo / "src" / "old" / "sub" / "x.py")

            findings = check_deprecated_path_used(repo, _config(repo))

            self.assertEqual(len(findings), 1)  # not two, despite both prefixes matching
            self.assertEqual(findings[0].meta["deprecated_path"], "src/old/sub")
            self.assertIn("src/newer", findings[0].recommendation)

    def test_missing_structure_map_yields_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "old" / "legacy.py")

            self.assertEqual(check_deprecated_path_used(repo, _config(repo)), [])


if __name__ == "__main__":
    unittest.main()
