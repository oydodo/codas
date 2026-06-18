from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.adapters.python import extract_import_facts


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


PACKAGE_FILES = (
    "pkg/__init__.py",
    "pkg/a.py",
    "pkg/b.py",
    "pkg/sub/__init__.py",
    "pkg/sub/c.py",
)


def _build(repo: Path) -> None:
    # __init__ imports a sibling module -> exercises the importer-is-__init__ path.
    _write(repo / "pkg" / "__init__.py", "from . import b\n")
    # module-level + function-local imports (both reachable via ast.walk).
    _write(
        repo / "pkg" / "b.py",
        "import json\n\n\ndef helper():\n    import csv\n    return csv\n",
    )
    # external, aliased, relative, and a name that is a symbol (not a submodule).
    _write(
        repo / "pkg" / "a.py",
        "import os\n"
        "import os.path as osp\n"
        "from . import b\n"
        "from pkg import b as bb\n"
        "from pkg.b import helper\n",
    )
    _write(repo / "pkg" / "sub" / "__init__.py", "")
    # bare/relative parents, a symbol name, and an over-deep relative import.
    _write(
        repo / "pkg" / "sub" / "c.py",
        "from .. import b\n"
        "from ..a import handle\n"
        "from . import not_a_module\n"
        "from ...deep import x\n",
    )


def _facts(repo: Path):
    return extract_import_facts(repo, PACKAGE_FILES)


class ImportFactsTests(unittest.TestCase):
    def test_relative_and_absolute_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            edges = {(f.module, f.target, f.target_path) for f in _facts(repo).imports}

            self.assertIn(("pkg/a.py", "pkg.b", "pkg/b.py"), edges)
            self.assertIn(("pkg/a.py", "pkg", "pkg/__init__.py"), edges)
            self.assertIn(("pkg/sub/c.py", "pkg.b", "pkg/b.py"), edges)
            self.assertIn(("pkg/sub/c.py", "pkg.a", "pkg/a.py"), edges)

    def test_init_module_is_an_importer_and_a_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            facts = _facts(repo).imports
            init_edges = {(f.target, f.target_path) for f in facts if f.module == "pkg/__init__.py"}
            paths = {f.target: f.target_path for f in facts}

            # __init__ (package "pkg") imports pkg.b; and pkg resolves to its __init__.
            self.assertIn(("pkg.b", "pkg/b.py"), init_edges)
            self.assertEqual(paths.get("pkg"), "pkg/__init__.py")

    def test_external_and_aliased_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            facts = _facts(repo).imports
            externals = {f.target: f.target_path for f in facts if f.target_path is None}

            # asname is ignored; the dotted target is the real module name.
            self.assertIsNone(externals.get("os"))
            self.assertIn("os.path", externals)  # `import os.path as osp`
            self.assertIn("json", externals)     # module-level in b.py
            self.assertIn("csv", externals)      # function-local in b.py (ast.walk)
            # `from pkg import b as bb` still records the pkg.b first-party edge.
            self.assertIn(
                ("pkg/a.py", "pkg.b"), {(f.module, f.target) for f in facts}
            )

    def test_symbol_name_is_not_a_phantom_edge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            targets = {f.target for f in _facts(repo).imports}

            self.assertIn("pkg.b", targets)
            self.assertNotIn("pkg.b.helper", targets)
            self.assertNotIn("pkg.sub.not_a_module", targets)

    def test_over_deep_relative_with_module_component_is_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            # `from ...deep import x` in pkg.sub climbs above the top package.
            c_targets = {f.target for f in _facts(repo).imports if f.module == "pkg/sub/c.py"}

            self.assertNotIn("deep", c_targets)
            self.assertNotIn("pkg.deep", c_targets)

    def test_same_target_on_multiple_lines_collapses_to_one_edge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            # a.py references pkg.b on three lines (3,4,5) -> one edge at first line.
            pkg_b = [
                f for f in _facts(repo).imports
                if f.module == "pkg/a.py" and f.target == "pkg.b"
            ]

            self.assertEqual(len(pkg_b), 1)
            self.assertEqual(pkg_b[0].line, 3)

    def test_total_sort_and_global_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _build(repo)

            facts = _facts(repo).imports
            sort_keys = [(f.module, f.line, f.target) for f in facts]
            edge_keys = [(f.module, f.target) for f in facts]

            self.assertEqual(sort_keys, sorted(sort_keys))
            self.assertEqual(len(edge_keys), len(set(edge_keys)))  # one edge per (module, target)

    def test_star_import_records_only_the_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "b.py", "x = 1\n")
            _write(repo / "pkg" / "a.py", "from pkg.b import *\n")

            targets = {
                f.target
                for f in extract_import_facts(repo, ("pkg/__init__.py", "pkg/a.py", "pkg/b.py")).imports
            }

            self.assertIn("pkg.b", targets)
            self.assertNotIn("pkg.b.*", targets)

    def test_root_level_init_does_not_prefix_a_dot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            # A root-level __init__.py makes "" a package dir; foo must stay "foo".
            _write(repo / "__init__.py", "")
            _write(repo / "foo.py", "x = 1\n")
            _write(repo / "bar.py", "import foo\n")

            paths = {
                f.target: f.target_path
                for f in extract_import_facts(repo, ("__init__.py", "bar.py", "foo.py")).imports
            }

            self.assertEqual(paths.get("foo"), "foo.py")  # not ".foo"

    def test_unparseable_file_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "bad.py", "def (:\n")

            facts = extract_import_facts(repo, ("pkg/__init__.py", "pkg/bad.py"))

            self.assertEqual(facts.skipped, ("pkg/bad.py",))


if __name__ == "__main__":
    unittest.main()
