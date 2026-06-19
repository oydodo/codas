from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.adapters.callgraph import extract_call_facts


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


A_PY = """\
from pkg.b import target
import pkg.b as b


def helper():
    pass


def caller():
    helper()        # direct
    target()        # imported_symbol
    b.other()       # module_attribute (distinct callee)
    print("noise")  # builtin -> dropped


class C:
    def m1(self):
        pass

    def m2(self):
        self.m1()   # self_method
        undefined()  # unresolved -> dropped
"""

B_PY = "def target():\n    pass\n\n\ndef other():\n    pass\n"


def _fixture(repo: Path) -> tuple[str, ...]:
    _write(repo / "pkg" / "__init__.py", "")
    _write(repo / "pkg" / "a.py", A_PY)
    _write(repo / "pkg" / "b.py", B_PY)
    return (
        "pkg/__init__.py",
        "pkg/a.py",
        "pkg/b.py",
    )


def _tuples(repo: Path):
    edges = extract_call_facts(repo, _fixture(repo)).edges
    return {
        (e.caller_symbol, e.callee_symbol, e.callee_path, e.resolution) for e in edges
    }


class ExtractCallFactsTests(unittest.TestCase):
    def test_resolution_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            got = _tuples(repo)
            self.assertIn(("caller", "helper", "pkg/a.py", "direct"), got)
            self.assertIn(("caller", "target", "pkg/b.py", "imported_symbol"), got)
            self.assertIn(("caller", "other", "pkg/b.py", "module_attribute"), got)
            self.assertIn(("m2", "m1", "pkg/a.py", "self_method"), got)

    def test_non_first_party_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            callees = {c for (_, c, _, _) in _tuples(repo)}
            self.assertNotIn("print", callees)      # builtin
            self.assertNotIn("undefined", callees)  # unresolved name

    def test_loose_files_out_of_scope(self) -> None:
        # a .py not inside a package (no __init__.py) yields no edges.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "loose.py", "def a():\n    b()\ndef b():\n    pass\n")
            self.assertEqual(extract_call_facts(repo, ("loose.py",)).edges, ())

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            files = _fixture(repo)
            self.assertEqual(
                extract_call_facts(repo, files), extract_call_facts(repo, files)
            )

    def test_shadowed_import_not_an_edge(self) -> None:
        # `target = 1; target()` must NOT resolve to the imported pkg.b.target.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "b.py", "def target():\n    pass\n")
            _write(
                repo / "pkg" / "a.py",
                "from pkg.b import target\n\n\ndef caller():\n    target = 1\n    target()\n    return target\n",
            )
            files = ("pkg/__init__.py", "pkg/a.py", "pkg/b.py")
            callees = {e.callee_symbol for e in extract_call_facts(repo, files).edges}
            self.assertNotIn("target", callees)

    def test_nested_def_call_not_attributed_to_outer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "__init__.py", "")
            _write(
                repo / "pkg" / "a.py",
                "def helper():\n    pass\n\n\ndef outer():\n    if True:\n        def inner():\n            helper()\n",
            )
            files = ("pkg/__init__.py", "pkg/a.py")
            edges = extract_call_facts(repo, files).edges
            self.assertEqual(
                [e for e in edges if e.caller_symbol == "outer"], []
            )

    def test_duplicate_method_names_kept_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "__init__.py", "")
            _write(
                repo / "pkg" / "a.py",
                "class A:\n    def run(self):\n        pass\n\n    def go(self):\n        self.run()\n\n\n"
                "class B:\n    def run(self):\n        pass\n\n    def go(self):\n        self.run()\n",
            )
            edges = extract_call_facts(repo, ("pkg/__init__.py", "pkg/a.py")).edges
            sm = [e for e in edges if e.caller_symbol == "go" and e.resolution == "self_method"]
            # A.go -> A.run and B.go -> B.run: class-scoped, NOT collapsed by dedup
            self.assertEqual(
                {(e.caller_class, e.callee_class) for e in sm}, {("A", "A"), ("B", "B")}
            )
            self.assertEqual(len({e.callee_line for e in sm}), 2)  # distinct class methods

    def test_relative_import_from_package_init(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "b.py", "def target():\n    pass\n")
            _write(
                repo / "pkg" / "__init__.py",
                "from .b import target\n\n\ndef caller():\n    target()\n",
            )
            edges = extract_call_facts(repo, ("pkg/__init__.py", "pkg/b.py")).edges
            self.assertTrue(
                any(e.caller_symbol == "caller" and e.callee_symbol == "target"
                    and e.callee_path == "pkg/b.py" and e.resolution == "imported_symbol"
                    for e in edges)
            )

    def test_lines_populated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            edge = next(
                e for e in extract_call_facts(repo, _fixture(repo)).edges
                if e.caller_symbol == "caller" and e.callee_symbol == "helper"
            )
            self.assertGreater(edge.caller_line, 0)
            self.assertGreater(edge.callee_line, 0)


if __name__ == "__main__":
    unittest.main()
