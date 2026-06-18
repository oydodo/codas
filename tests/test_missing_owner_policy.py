from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.policies.missing_owner import (
    check_missing_structure_owner,
    nearest_candidate_units,
)
from codas.structure.models import StructureUnit

# Covers .codas (so the fixture's own structure.yml is owned) and src/foo, leaving
# only deliberately-placed files unowned.
MAP_NO_ROOT = """\
version: 1
kind: structure_map
units:
  codas-unit:
    path: .codas
    kind: governance_state
    owner: Core
    purpose: x
    canonical_placement: x
  src-foo-unit:
    path: src/foo
    kind: package
    owner: Core
    purpose: x
    canonical_placement: x
"""

MAP_WITH_ROOT = """\
version: 1
kind: structure_map
units:
  repo-root:
    path: .
    kind: repository
    owner: Core
    purpose: x
    canonical_placement: x
"""


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _unit(unit_id: str, path: str) -> StructureUnit:
    return StructureUnit(
        id=unit_id,
        path=path,
        kind="package",
        owner="Core",
        purpose="x",
        canonical_placement="x",
    )


class MissingStructureOwnerPolicyTests(unittest.TestCase):
    def test_unowned_file_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", MAP_NO_ROOT)
            _write(repo / "src" / "foo" / "keep.py")  # owned by src-foo-unit
            _write(repo / "src" / "bar.py")  # under src/ but no unit covers it

            findings = check_missing_structure_owner(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            finding = findings[0]
            self.assertEqual(finding.check_id, "missing-structure-owner")
            self.assertEqual(finding.severity, "error")
            self.assertEqual(finding.evidence[0].path, "src/bar.py")
            # shares the leading "src" component with src-foo-unit only
            self.assertEqual(finding.meta["nearest_candidates"], ["src-foo-unit"])

    def test_root_catch_all_covers_everything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", MAP_WITH_ROOT)
            _write(repo / "src" / "keep.py")
            _write(repo / "top.md")

            self.assertEqual(check_missing_structure_owner(repo, _config(repo)), [])

    def test_findings_sorted_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", MAP_NO_ROOT)
            _write(repo / "b.md")
            _write(repo / "a.md")

            findings = check_missing_structure_owner(repo, _config(repo))

            self.assertEqual(
                [f.evidence[0].path for f in findings], ["a.md", "b.md"]
            )

    def test_missing_structure_map_yields_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "top.md")

            self.assertEqual(check_missing_structure_owner(repo, _config(repo)), [])


class NearestCandidateTests(unittest.TestCase):
    def test_deeper_unit_ranks_first(self) -> None:
        units = (_unit("src-unit", "src"), _unit("foo-unit", "src/foo"))

        candidates = nearest_candidate_units("src/foo/bar.py", units)

        self.assertEqual(candidates, ["foo-unit", "src-unit"])

    def test_no_overlap_falls_back_to_all_sorted_by_id(self) -> None:
        units = (_unit("z-unit", "lib"), _unit("a-unit", "vendor"))

        candidates = nearest_candidate_units("top.md", units)

        self.assertEqual(candidates, ["a-unit", "z-unit"])

    def test_capped_at_three(self) -> None:
        units = tuple(_unit(f"u{i}", f"p{i}") for i in range(5))

        self.assertEqual(len(nearest_candidate_units("top.md", units)), 3)

    def test_glob_unit_scored_on_literal_head(self) -> None:
        # src/*/x contributes literal head "src"; the literal src/foo wins on depth.
        units = (_unit("glob-unit", "src/*/x"), _unit("lit-unit", "src/foo"))

        candidates = nearest_candidate_units("src/foo/bar.py", units)

        self.assertEqual(candidates, ["lit-unit", "glob-unit"])

    def test_pure_glob_unit_has_no_literal_head(self) -> None:
        # "*" → empty literal head → shared 0; src-unit has real overlap, so the
        # zero-overlap star is excluded (positive overlap suppresses the fallback).
        units = (_unit("star", "*"), _unit("src-unit", "src"))

        self.assertEqual(nearest_candidate_units("src/bar.py", units), ["src-unit"])

    def test_single_component_artifact_and_unit(self) -> None:
        units = (_unit("readme-area", "README.md"), _unit("src-unit", "src"))

        # "top.md" shares no leading component with either → fallback, sorted by id
        self.assertEqual(
            nearest_candidate_units("top.md", units), ["readme-area", "src-unit"]
        )
        # "README.md" shares its single component with readme-area only
        self.assertEqual(
            nearest_candidate_units("README.md", units), ["readme-area"]
        )


if __name__ == "__main__":
    unittest.main()
