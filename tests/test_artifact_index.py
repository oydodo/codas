from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.structure.index import build_artifact_index, normalize_path
from codas.structure.models import StructureMap, StructureUnit


def _unit(unit_id: str, path: str) -> StructureUnit:
    return StructureUnit(
        id=unit_id,
        path=path,
        kind="package",
        owner="Core",
        purpose="x",
        canonical_placement="x",
    )


MAP = StructureMap(
    version=1,
    kind="structure_map",
    units=(
        _unit("root", "."),
        _unit("src", "src"),
        _unit("policies", "src/policies"),
    ),
)


def _write(path: Path, text: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class ArtifactIndexTests(unittest.TestCase):
    def test_normalize_root_to_empty(self) -> None:
        self.assertEqual(normalize_path("."), "")
        self.assertEqual(normalize_path("./src/"), "src")
        self.assertEqual(normalize_path("src/policies"), "src/policies")

    def test_deepest_unit_owns_nested_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "README.md")
            _write(repo / "src" / "cli.py")
            _write(repo / "src" / "policies" / "rule.py")

            index = build_artifact_index(repo, (".",), MAP)

            # root owns everything (subtree), src owns its subtree, policies its own
            self.assertEqual(index.observations["root"].artifact_count, 3)
            self.assertEqual(index.observations["src"].artifact_count, 2)
            self.assertEqual(index.observations["policies"].artifact_count, 1)
            self.assertEqual(index.unowned, ())  # root catches the remainder

    def test_pycache_excluded_in_walk_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "cli.py")
            _write(repo / "src" / "__pycache__" / "cli.cpython.pyc")

            index = build_artifact_index(repo, (".",), MAP)
            self.assertNotIn("src/__pycache__/cli.cpython.pyc", index.files)

    def test_walk_fallback_when_git_missing(self) -> None:
        import codas.structure.index as index_mod

        original = index_mod.subprocess.run

        def boom(*args, **kwargs):
            raise FileNotFoundError("git")

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "cli.py")
            index_mod.subprocess.run = boom
            try:
                index = build_artifact_index(repo, (".",), MAP)
            finally:
                index_mod.subprocess.run = original
            self.assertIn("src/cli.py", index.files)

    def test_unowned_when_no_root_unit(self) -> None:
        no_root = StructureMap(
            version=1, kind="structure_map", units=(_unit("src", "src"),)
        )
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "README.md")
            _write(repo / "src" / "cli.py")

            index = build_artifact_index(repo, (".",), no_root)
            self.assertIn("README.md", index.unowned)
            self.assertNotIn("src/cli.py", index.unowned)

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_gitignored_file_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            _write(repo / ".gitignore", "*.log\n")
            _write(repo / "src" / "keep.py")
            _write(repo / "src" / "drop.log")

            index = build_artifact_index(repo, (".",), MAP)
            self.assertIn("src/keep.py", index.files)
            self.assertNotIn("src/drop.log", index.files)


if __name__ == "__main__":
    unittest.main()
