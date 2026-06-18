from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.adapters.python import extract_symbol_facts


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class PythonAdapterTests(unittest.TestCase):
    def test_top_level_class_and_function(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "mod.py", "class Foo:\n    pass\n\n\ndef bar():\n    return 1\n")

            facts = extract_symbol_facts(repo, ("mod.py",))

            self.assertEqual(facts.skipped, ())
            self.assertEqual(
                [(d.name, d.kind, d.line) for d in facts.definitions],
                [("Foo", "class", 1), ("bar", "function", 5)],
            )

    def test_async_function_is_function_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "a.py", "async def go():\n    pass\n")

            facts = extract_symbol_facts(repo, ("a.py",))

            self.assertEqual([(d.name, d.kind) for d in facts.definitions], [("go", "function")])

    def test_nested_and_method_symbols_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / "n.py",
                "class C:\n"
                "    def method(self):\n"
                "        pass\n"
                "\n"
                "def outer():\n"
                "    def inner():\n"
                "        pass\n",
            )

            facts = extract_symbol_facts(repo, ("n.py",))

            # only the top-level class C and function outer; method/inner excluded
            self.assertEqual(
                [d.name for d in facts.definitions], ["C", "outer"]
            )

    def test_syntax_error_is_skipped_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "broken.py", "def (:\n")
            _write(repo / "ok.py", "def fine():\n    pass\n")

            facts = extract_symbol_facts(repo, ("broken.py", "ok.py"))

            self.assertEqual(facts.skipped, ("broken.py",))
            self.assertEqual([d.name for d in facts.definitions], ["fine"])

    def test_non_python_files_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "notes.md", "def looks_like_code(): pass\n")

            facts = extract_symbol_facts(repo, ("notes.md",))

            self.assertEqual(facts.definitions, ())
            self.assertEqual(facts.skipped, ())

    def test_empty_and_import_only_module_has_no_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "e.py", "import os\nfrom sys import path\n")

            facts = extract_symbol_facts(repo, ("e.py",))

            self.assertEqual(facts.definitions, ())
            self.assertEqual(facts.skipped, ())

    def test_definitions_sorted_across_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "b.py", "def dup():\n    pass\n")
            _write(repo / "a.py", "def dup():\n    pass\n")

            facts = extract_symbol_facts(repo, ("b.py", "a.py"))

            self.assertEqual(
                [(d.module, d.name) for d in facts.definitions],
                [("a.py", "dup"), ("b.py", "dup")],
            )


if __name__ == "__main__":
    unittest.main()
