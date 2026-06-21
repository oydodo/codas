from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.structure.index import (
    DERIVED_OUTPUT_DEFAULT,
    build_artifact_index,
    derived_output_prefixes,
    filter_to_roots,
    is_derived_output,
    normalize_path,
)
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

    def test_wiki_book_excluded_in_walk_fallback(self) -> None:
        # The root `wiki/` book is a derived-output prefix: dropped at filter_to_roots, so
        # it never enters the scanned set (would otherwise break byte-identical inventory).
        import codas.structure.index as index_mod

        original = index_mod.subprocess.run

        def boom(*args, **kwargs):
            raise FileNotFoundError("git")

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "cli.py")
            _write(repo / "wiki" / "index.md")
            _write(repo / "wiki" / "codas-app.md")
            index_mod.subprocess.run = boom
            try:
                index = build_artifact_index(repo, (".",), MAP)
            finally:
                index_mod.subprocess.run = original
            self.assertIn("src/cli.py", index.files)
            self.assertNotIn("wiki/index.md", index.files)
            self.assertNotIn("wiki/codas-app.md", index.files)
            self.assertEqual(index.unowned, ())  # the book is not unowned — it is invisible

    def test_filter_to_roots_drops_derived_output(self) -> None:
        # filter_to_roots is the ONE chokepoint shared by discover_files AND head_snapshot
        # (the HEAD fact baseline). Excluding here covers both — a wiki/*.py can never enter
        # the fact_delta snapshot. Prefix-boundary: `wikipedia.py` at root is NOT excluded.
        selected = filter_to_roots(
            ["wiki/index.md", "wiki/sub/x.py", "wikipedia.py", "src/codas/x.py"], (".",)
        )
        self.assertEqual(selected, ["src/codas/x.py", "wikipedia.py"])

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_wiki_book_excluded_git_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            _write(repo / "src" / "keep.py")
            _write(repo / "wiki" / "index.md")  # untracked-not-ignored -> git ls-files --others
            index = build_artifact_index(repo, (".",), MAP)
            self.assertIn("src/keep.py", index.files)
            self.assertNotIn("wiki/index.md", index.files)

    def test_derived_prefix_opt_out_keeps_wiki_in_scan(self) -> None:
        # With the reservation opted out (derived_prefixes=()), a real wiki/ dir is governed
        # normally — filter_to_roots keeps it (parity with a user setting wiki.book_root: "").
        selected = filter_to_roots(
            ["wiki/index.md", "src/codas/x.py"], (".",), derived_prefixes=()
        )
        self.assertEqual(selected, ["src/codas/x.py", "wiki/index.md"])

    def test_custom_derived_prefix_reserves_that_root(self) -> None:
        selected = filter_to_roots(
            ["docs/book/x.md", "wiki/keep.md", "src/y.py"],
            (".",),
            derived_prefixes=("docs/book",),
        )
        # docs/book is reserved; wiki/ is NOT (the knob moved the reservation).
        self.assertEqual(selected, ["src/y.py", "wiki/keep.md"])

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


class DerivedOutputResolverTests(unittest.TestCase):
    def test_default_when_unset_or_no_knob(self) -> None:
        self.assertEqual(derived_output_prefixes({}), DERIVED_OUTPUT_DEFAULT)
        self.assertEqual(derived_output_prefixes({"wiki": {}}), DERIVED_OUTPUT_DEFAULT)
        self.assertEqual(DERIVED_OUTPUT_DEFAULT, ("wiki",))

    def test_explicit_empty_is_opt_out(self) -> None:
        self.assertEqual(derived_output_prefixes({"wiki": {"book_root": ""}}), ())

    def test_null_falls_back_to_default(self) -> None:
        # `book_root:` (bare null) is NOT the opt-out; the opt-out is an explicit "".
        self.assertEqual(
            derived_output_prefixes({"wiki": {"book_root": None}}), DERIVED_OUTPUT_DEFAULT
        )

    def test_custom_path_normalized(self) -> None:
        self.assertEqual(
            derived_output_prefixes({"wiki": {"book_root": ".\\docs/book/"}}),
            ("docs/book",),
        )

    def test_is_derived_output_prefix_boundary(self) -> None:
        self.assertTrue(is_derived_output("wiki", ("wiki",)))
        self.assertTrue(is_derived_output("wiki/x.md", ("wiki",)))
        self.assertFalse(is_derived_output("wikipedia.py", ("wiki",)))
        self.assertFalse(is_derived_output("wiki/x.md", ()))  # opted out -> never derived


if __name__ == "__main__":
    unittest.main()
