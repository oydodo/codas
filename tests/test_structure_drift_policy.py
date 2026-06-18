from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.policies.structure_drift import check_structure_drift


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _map(*unit_blocks: str) -> str:
    return "version: 1\nkind: structure_map\nunits:\n" + "".join(unit_blocks)


def _unit(unit_id: str, path: str, status: str = "active") -> str:
    return (
        f"  {unit_id}:\n"
        f"    path: {path}\n"
        f"    kind: package\n"
        f"    owner: Core\n"
        f"    purpose: x\n"
        f"    canonical_placement: x\n"
        f"    status: {status}\n"
    )


class StructureDriftPolicyTests(unittest.TestCase):
    def test_active_unit_with_missing_path_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", _map(_unit("gone", "src/gone")))

            findings = check_structure_drift(repo, _config(repo))

            self.assertEqual(len(findings), 1)
            finding = findings[0]
            self.assertEqual(finding.check_id, "structure-drift")
            self.assertEqual(finding.severity, "error")
            self.assertEqual(finding.meta["unit"], "gone")
            self.assertEqual(finding.meta["path"], "src/gone")
            self.assertEqual(finding.evidence[0].path, ".codas/structure.yml")

    def test_active_unit_with_existing_path_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", _map(_unit("here", "src/here")))
            _write(repo / "src" / "here" / "keep.py")

            self.assertEqual(check_structure_drift(repo, _config(repo)), [])

    def test_file_path_unit_existence_is_honored(self) -> None:
        # Locks that the existence check covers file paths (not just directories),
        # matching build_artifact_index literal-exists semantics (Path.exists()).
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "structure.yml",
                _map(
                    _unit("present-file", "pyproject.toml"),
                    _unit("absent-file", "missing.toml"),
                ),
            )
            _write(repo / "pyproject.toml")

            findings = check_structure_drift(repo, _config(repo))

            self.assertEqual([f.meta["unit"] for f in findings], ["absent-file"])

    def test_planned_unit_with_missing_path_is_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "structure.yml",
                _map(_unit("future", "src/future", status="planned")),
            )

            self.assertEqual(check_structure_drift(repo, _config(repo)), [])

    def test_root_and_glob_units_are_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "structure.yml",
                _map(_unit("root", "."), _unit("globbed", "src/*/gen")),
            )

            self.assertEqual(check_structure_drift(repo, _config(repo)), [])

    def test_findings_sorted_by_unit_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "structure.yml",
                _map(_unit("z-gone", "src/z"), _unit("a-gone", "src/a")),
            )

            findings = check_structure_drift(repo, _config(repo))

            self.assertEqual([f.meta["unit"] for f in findings], ["a-gone", "z-gone"])

    def test_missing_structure_map_yields_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self.assertEqual(check_structure_drift(repo, _config(repo)), [])


if __name__ == "__main__":
    unittest.main()
