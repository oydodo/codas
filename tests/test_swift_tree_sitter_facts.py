from __future__ import annotations

import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codas.adapters.git import list_paths_at_head
from codas.adapters.python import ImportFacts, SymbolFact, SymbolFacts
from codas.adapters.swift import extract_swift_imports, extract_swift_symbols
from codas.adapters.swift_parse import parse_swift_sources
from codas.config.loader import CodasConfig
from codas.facts.context import build_scan_context
from codas.facts.snapshot import merge_import_facts, merge_symbol_facts, head_snapshot


def _swift_available() -> bool:
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            parsed = parse_swift_sources({"Sources/App.swift": "public struct App {}\n"})
    except Exception:
        return False
    return parsed.unavailable is None and parsed.modules and parsed.modules[0].tree is not None


SWIFT_AVAILABLE = _swift_available()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


def _commit(repo: Path, msg: str = "c") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


class SwiftGracefulDegradeTests(unittest.TestCase):
    def test_swift_unavailable_records_skipped_without_raise(self) -> None:
        import codas.adapters.swift_parse as swift_parse

        swift_parse._UNAVAILABLE_NOTICE_EMITTED = False
        with mock.patch("codas.adapters.swift_parse._swift_parser", return_value=(None, "missing")):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                parsed = parse_swift_sources({"Sources/App.swift": "struct App {}\n"})
        self.assertEqual(parsed.unavailable, "missing")
        self.assertEqual([module.path for module in parsed.modules], ["Sources/App.swift"])
        self.assertIsNone(parsed.modules[0].tree)
        self.assertIn("Swift extraction unavailable", stderr.getvalue())

    def test_empty_extra_merge_preserves_identity(self) -> None:
        symbols = SymbolFacts((SymbolFact("pkg/a.py", "run", "function", 1),), ())
        imports = ImportFacts((), ())
        self.assertIs(merge_symbol_facts(symbols, SymbolFacts((), ())), symbols)
        self.assertIs(merge_import_facts(imports, ImportFacts((), ())), imports)

    def test_python_only_facts_and_delta_stay_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "a.py", "def run():\n    pass\n")
            _commit(repo)

            first = build_scan_context(repo, _config(repo))
            second = build_scan_context(repo, _config(repo))
            self.assertEqual(first.symbols(), second.symbols())
            self.assertEqual(
                first.symbols().definitions,
                (SymbolFact("pkg/a.py", "run", "function", 1),),
            )
            self.assertEqual(first.symbols().skipped, ())
            self.assertEqual(first.imports(), second.imports())
            self.assertTrue(first.fact_delta().is_empty())


class HeadPathListerTests(unittest.TestCase):
    def test_list_paths_at_head_filters_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _write(repo / "pkg" / "a.py", "def run():\n    pass\n")
            _write(repo / "Sources" / "App.swift", "struct App {}\n")
            _write(repo / "README.md", "# doc\n")
            _commit(repo)

            both = list_paths_at_head(repo, (".py", ".swift"))
            py_only = list_paths_at_head(repo, (".py",))
            self.assertEqual([path for path, _ in both or ()], ["Sources/App.swift", "pkg/a.py"])
            self.assertEqual([path for path, _ in py_only or ()], ["pkg/a.py"])


@unittest.skipUnless(SWIFT_AVAILABLE, "tree-sitter Swift extra unavailable")
class SwiftExtractionTests(unittest.TestCase):
    def test_swift_symbols_and_imports(self) -> None:
        source = """
import Foundation
import UIKit.UIView

public final class Box {}
struct Bag {}
struct Outer {
  struct Inner {}
}
enum State {}
actor Worker {}
protocol Runnable {}
func run() {}
typealias Name = String
extension Box {}
"""
        parsed = parse_swift_sources({"Sources/App.swift": source})
        symbols = extract_swift_symbols(parsed)
        imports = extract_swift_imports(parsed)

        got = {(fact.name, fact.kind) for fact in symbols.definitions}
        self.assertEqual(
            got,
            {
                ("Box", "class"),
                ("Bag", "struct"),
                ("Outer", "struct"),
                ("State", "enum"),
                ("Worker", "actor"),
                ("Runnable", "protocol"),
                ("run", "function"),
                ("Name", "typealias"),
            },
        )
        self.assertNotIn(("Box", "extension"), got)
        self.assertEqual(
            [(fact.target, fact.target_path) for fact in imports.imports],
            [("Foundation", None), ("UIKit.UIView", None)],
        )

    def test_swift_type_references_emit_first_party_edges(self) -> None:
        parsed = parse_swift_sources(
            {
                "Sources/Agent.swift": """
public protocol AgentRunnable {}
public struct AgentRuntime {}
public struct KnowledgeStore {}
public struct ViewModel<T> {}
""",
                "Sources/UI.swift": """
import SwiftUI
struct DashboardView: AgentRunnable {
  let agent: AgentRuntime
  var agents: [AgentRuntime]
  func render(input: AgentRuntime, store: KnowledgeStore) -> ViewModel<AgentRuntime> {
    fatalError()
  }
}
""",
            }
        )

        imports = extract_swift_imports(parsed)
        edges = {
            (fact.module, fact.target, fact.target_path)
            for fact in imports.imports
            if fact.target_path is not None
        }

        self.assertEqual(
            edges,
            {
                ("Sources/UI.swift", "AgentRunnable", "Sources/Agent.swift"),
                ("Sources/UI.swift", "AgentRuntime", "Sources/Agent.swift"),
                ("Sources/UI.swift", "KnowledgeStore", "Sources/Agent.swift"),
                ("Sources/UI.swift", "ViewModel", "Sources/Agent.swift"),
            },
        )
        self.assertIn(
            ("SwiftUI", None),
            {(fact.target, fact.target_path) for fact in imports.imports},
        )

    def test_swift_ambiguous_type_reference_emits_no_edge(self) -> None:
        parsed = parse_swift_sources(
            {
                "Sources/A/Store.swift": "struct Store {}\n",
                "Sources/B/Store.swift": "struct Store {}\n",
                "Sources/UI.swift": "struct UI { let store: Store }\n",
            }
        )

        imports = extract_swift_imports(parsed)

        self.assertEqual(
            [
                (fact.module, fact.target, fact.target_path)
                for fact in imports.imports
                if fact.target == "Store"
            ],
            [],
        )

    def test_swift_malformed_file_records_parse_diagnostic(self) -> None:
        parsed = parse_swift_sources({"Sources/Broken.swift": "struct {"})
        symbols = extract_swift_symbols(parsed)
        imports = extract_swift_imports(parsed)
        self.assertEqual(symbols.definitions, ())
        self.assertEqual(len(symbols.skipped), 1)
        self.assertTrue(symbols.skipped[0].startswith("Sources/Broken.swift:1:"))
        self.assertIn("ERROR", symbols.skipped[0])
        self.assertEqual(imports.imports, ())
        self.assertEqual(imports.skipped, symbols.skipped)

    def test_swift_partial_parse_keeps_valid_symbols_and_reference_edges(self) -> None:
        parsed = parse_swift_sources(
            {
                "Sources/Shared.swift": "struct CredentialService {}\n",
                "Sources/App.swift": """
struct ToolDispatcher {
  let credentialService: CredentialService
  func run() {
    nonisolated(unsafe) let arguments: [String: Any] = [:]
  }
}
""",
            }
        )

        symbols = extract_swift_symbols(parsed)
        imports = extract_swift_imports(parsed)

        self.assertIn(
            ("Sources/App.swift", "ToolDispatcher", "struct"),
            {(fact.module, fact.name, fact.kind) for fact in symbols.definitions},
        )
        self.assertIn(
            ("Sources/Shared.swift", "CredentialService", "struct"),
            {(fact.module, fact.name, fact.kind) for fact in symbols.definitions},
        )
        self.assertIn(
            ("Sources/App.swift", "CredentialService", "Sources/Shared.swift"),
            {(fact.module, fact.target, fact.target_path) for fact in imports.imports},
        )
        self.assertEqual(len(symbols.skipped), 1)
        self.assertIn("nonisolated(unsafe)", symbols.skipped[0])
        self.assertEqual(imports.skipped, symbols.skipped)

    def test_mixed_merge_orders_deterministically(self) -> None:
        python = SymbolFacts((SymbolFact("pkg/z.py", "py_symbol", "function", 10),), ())
        swift = SymbolFacts((SymbolFact("Sources/App.swift", "App", "struct", 1),), ())
        merged = merge_symbol_facts(python, swift)
        self.assertEqual(
            [(fact.module, fact.name) for fact in merged.definitions],
            [("Sources/App.swift", "App"), ("pkg/z.py", "py_symbol")],
        )

    def test_head_snapshot_swift_delta_symmetric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _write(repo / "Sources" / "App.swift", "struct OldName {}\n")
            _commit(repo)

            snap = head_snapshot(repo, (".",))
            self.assertIsNotNone(snap)
            self.assertIn(
                ("Sources/App.swift", "OldName", "struct"),
                {(fact.module, fact.name, fact.kind) for fact in snap.symbols.definitions},
            )

            clean = build_scan_context(repo, _config(repo))
            self.assertTrue(clean.fact_delta().is_empty())

            _write(repo / "Sources" / "App.swift", "struct NewName {}\n")
            dirty = build_scan_context(repo, _config(repo))
            delta = dirty.fact_delta()
            self.assertEqual(
                delta.symbols_removed,
                (("Sources/App.swift", "OldName", "struct"),),
            )
            self.assertEqual(
                delta.symbols_added,
                (("Sources/App.swift", "NewName", "struct"),),
            )

    def test_head_snapshot_swift_reference_delta_symmetric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _write(repo / "Sources" / "Agent.swift", "struct AgentRuntime {}\n")
            _write(repo / "Sources" / "UI.swift", "struct UI { let agent: AgentRuntime }\n")
            _commit(repo)

            clean = build_scan_context(repo, _config(repo))
            self.assertTrue(clean.fact_delta().is_empty())
            self.assertIn(
                ("Sources/UI.swift", "AgentRuntime", "Sources/Agent.swift"),
                {
                    (fact.module, fact.target, fact.target_path)
                    for fact in clean.imports().imports
                },
            )

            _write(repo / "Sources" / "UI.swift", "struct UI { let agent: MissingRuntime }\n")
            dirty = build_scan_context(repo, _config(repo))
            delta = dirty.fact_delta()
            self.assertIn(
                ("Sources/UI.swift", "AgentRuntime", "Sources/Agent.swift"),
                delta.imports_removed,
            )
            self.assertNotIn(
                ("Sources/UI.swift", "MissingRuntime", "Sources/Agent.swift"),
                delta.imports_added,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
