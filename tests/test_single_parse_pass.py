"""Slice-1 fact-cache: single parse pass + unified scan + exclude_under pre-filter.

These lock the three contracts the refactor introduces on TOP of the byte-identical
fact outputs (which the existing test_python_adapter / test_python_import_facts /
test_call_facts / test_inventory / test_scan_context suites already pin as golden
values written against the pre-refactor logic):

1. one ``ast.parse`` per ``.py`` per run (no per-accessor re-parse);
2. ``build_inventory`` projects from a ScanContext and is byte-identical whether it
   self-builds the scan or reuses a caller's ctx (the ``check --json`` reuse path);
3. ``exclude_under`` PRE-FILTERS the scanned file set before extraction, so Python
   import/call resolution (which is file-set-dependent) changes correctly — the
   codex design-review BLOCKER (post-filtering rows would not be behavior-preserving).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codas.adapters.python import extract_import_facts_from_parsed, extract_symbol_facts_from_parsed
from codas.adapters.callgraph import extract_call_facts_from_parsed
from codas.adapters.python_parse import parse_python_modules
from codas.app.inventory import render_inventory_json
from codas.config.loader import CodasConfig, load_codas_config
from codas.facts.context import ScanContext, build_scan_context
from codas.structure.inventory import build_inventory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


# A cross-package fixture: kept/ imports + calls into excluded/. Resolution of those
# edges depends on whether excluded/ is in the scanned set.
_KEPT_INIT = ""
_KEPT_A = """\
from excluded.target import do_thing
import excluded.target as t


def run():
    do_thing()      # imported_symbol -> excluded.target.do_thing
    t.other()       # module_attribute -> excluded.target.other
"""
_EXC_INIT = ""
_EXC_TARGET = "def do_thing():\n    pass\n\n\ndef other():\n    pass\n"


def _build_cross_package(repo: Path) -> tuple[str, ...]:
    _write(repo / "kept" / "__init__.py", _KEPT_INIT)
    _write(repo / "kept" / "a.py", _KEPT_A)
    _write(repo / "excluded" / "__init__.py", _EXC_INIT)
    _write(repo / "excluded" / "target.py", _EXC_TARGET)
    return (
        "kept/__init__.py",
        "kept/a.py",
        "excluded/__init__.py",
        "excluded/target.py",
    )


class SingleParsePassTests(unittest.TestCase):
    def test_scan_context_parses_each_file_once_across_accessors(self) -> None:
        # symbols() + imports() + calls() must share ONE parse pass, not 3.
        repo = Path.cwd()
        ctx = build_scan_context(repo, load_codas_config(repo / ".codas" / "config.yml"))

        real = parse_python_modules
        calls: list[int] = []

        def counting(repo_arg, files_arg):
            result = real(repo_arg, files_arg)
            calls.append(len(result.modules))
            return result

        with mock.patch("codas.facts.context.parse_python_modules", side_effect=counting):
            ctx.symbols()
            ctx.imports()
            ctx.calls()
            ctx.symbols()  # cached re-read must not re-parse

        self.assertEqual(len(calls), 1, "expected exactly one parse pass per run")
        # Each scanned .py appears exactly once in the single pass (no duplicate parse).
        py_count = sum(1 for f in ctx.files if f.endswith(".py"))
        self.assertEqual(calls[0], py_count)

    def test_unreadable_package_file_preserves_legacy_error_divergence(self) -> None:
        # Codex impl-review finding 2: legacy symbols/imports caught OSError (-> skip)
        # while callgraph caught only Syntax/ValueError (-> OSError propagated). The
        # shared parse must reproduce BOTH: read failure is skipped by symbols/imports
        # and re-raised by callgraph (so check --json provenance stays null, not a
        # concrete hash). A pure parse failure stays an errored/skipped module.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "a.py", "def f():\n    pass\n")
            files = ("pkg/__init__.py", "pkg/a.py")

            real_read = Path.read_bytes

            def fake_read(self, *a, **k):
                if self.name == "a.py":
                    raise OSError("unreadable")
                return real_read(self, *a, **k)

            with mock.patch.object(Path, "read_bytes", fake_read):
                parsed = parse_python_modules(repo, files)
                self.assertIn("pkg/a.py", extract_symbol_facts_from_parsed(parsed).skipped)
                self.assertIn("pkg/a.py", extract_import_facts_from_parsed(parsed).skipped)
                with self.assertRaises(OSError):
                    extract_call_facts_from_parsed(parsed)

    def test_parse_python_modules_is_one_entry_per_py_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            files = _build_cross_package(repo)
            parsed = parse_python_modules(repo, files)
            paths = [m.path for m in parsed.modules]
            self.assertEqual(paths, sorted(p for p in files if p.endswith(".py")))
            self.assertEqual(len(paths), len(set(paths)))
            self.assertTrue(all(m.tree is not None for m in parsed.modules))


class CtxReuseByteIdentityTests(unittest.TestCase):
    def test_build_inventory_with_reused_ctx_is_byte_identical(self) -> None:
        # The check --json provenance path passes the run's ScanContext into
        # build_inventory; the projected inventory must match a self-built scan byte
        # for byte (else the provenance inventory_hash would fork from `inventory`).
        repo = Path.cwd()
        ctx = build_scan_context(repo, load_codas_config(repo / ".codas" / "config.yml"))
        self.assertEqual(
            render_inventory_json(build_inventory(repo)),
            render_inventory_json(build_inventory(repo, ctx=ctx)),
        )


class ExcludeUnderPreFilterTests(unittest.TestCase):
    def test_resolution_is_file_set_dependent(self) -> None:
        # Proves WHY exclude_under must pre-filter: dropping the target file from the
        # scanned set changes the resolved facts of the *unchanged* importer.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            files = _build_cross_package(repo)
            kept_only = tuple(f for f in files if not f.startswith("excluded/"))

            full_imports = extract_import_facts_from_parsed(parse_python_modules(repo, files))
            cut_imports = extract_import_facts_from_parsed(parse_python_modules(repo, kept_only))

            full_target = {
                (i.module, i.target): i.target_path for i in full_imports.imports
            }
            cut_target = {
                (i.module, i.target): i.target_path for i in cut_imports.imports
            }
            # With excluded/ scanned, the import resolves first-party (has a path).
            self.assertEqual(
                full_target.get(("kept/a.py", "excluded.target")),
                "excluded/target.py",
            )
            # Pre-filtered out, the same importer's edge no longer resolves first-party.
            self.assertIsNone(cut_target.get(("kept/a.py", "excluded.target")))

            full_edges = extract_call_facts_from_parsed(parse_python_modules(repo, files))
            cut_edges = extract_call_facts_from_parsed(parse_python_modules(repo, kept_only))
            full_callees = {(e.caller_path, e.callee_path) for e in full_edges.edges}
            cut_callees = {(e.caller_path, e.callee_path) for e in cut_edges.edges}
            # The cross-package call edges exist only while the target is scanned.
            self.assertIn(("kept/a.py", "excluded/target.py"), full_callees)
            self.assertNotIn(("kept/a.py", "excluded/target.py"), cut_callees)

    def test_build_inventory_exclude_under_drops_subtree_and_unresolves_edges(self) -> None:
        # End-to-end on the real repo (the production exclude_under path the Atlas
        # pack uses): excluding src/codas/adapters removes its symbols AND turns a
        # cross-tree import edge into it first-party-unresolved (target_path None).
        repo = Path.cwd()
        full = build_inventory(repo)
        cut = build_inventory(repo, exclude_under=("src/codas/adapters",))

        full_sources = set((full["symbols"]).get("sources", []))
        cut_sources = set((cut["symbols"]).get("sources", []))
        self.assertTrue(any(s.startswith("src/codas/adapters/") for s in full_sources))
        self.assertFalse(any(s.startswith("src/codas/adapters/") for s in cut_sources))

        # facts/context.py imports codas.adapters.python — resolved while adapters are
        # scanned, unresolved once the subtree is pre-filtered out.
        def target_path(inv, module, target):
            for edge in inv["imports"]["edges"]:
                if edge["module"] == module and edge["target"] == target:
                    return edge["target_path"]
            return "MISSING"

        self.assertEqual(
            target_path(full, "src/codas/facts/context.py", "codas.adapters.python"),
            "src/codas/adapters/python.py",
        )
        self.assertIsNone(
            target_path(cut, "src/codas/facts/context.py", "codas.adapters.python")
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
