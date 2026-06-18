from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import codas.policies as policies_package
import codas.policies.stale_claim as stale_claim_module
from codas.adapters.markdown import extract_doc_claims
from codas.adapters.python import extract_import_facts, extract_symbol_facts
from codas.config.loader import CodasConfig
from codas.facts.context import ScanContext, build_scan_context


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _absolute_module(node: ast.ImportFrom, package: str) -> str:
    """Resolve an ImportFrom to an absolute dotted module name.

    Handles relative imports (``node.level > 0``) so a `from ..adapters.markdown`
    cannot evade the boundary guard. Mirrors CPython's relative-name resolution.
    """
    if node.level == 0:
        return node.module or ""
    base = package.rsplit(".", node.level - 1)[0]
    return f"{base}.{node.module}" if node.module else base


def _imported_modules(source_path: Path, package: str) -> list[str]:
    """Absolute dotted names of every module imported by a source file (AST-based).

    For ``from PKG import name`` both ``PKG`` and ``PKG.name`` are emitted, because
    ``name`` may itself be a submodule — so a bare ``from .. import adapters`` is
    surfaced as ``codas.adapters`` and cannot evade the boundary guard.
    """
    names: list[str] = []
    for node in ast.walk(ast.parse(source_path.read_text())):
        if isinstance(node, ast.ImportFrom):
            base = _absolute_module(node, package)
            if base:
                names.append(base)
                names.extend(f"{base}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


class ScanContextTests(unittest.TestCase):
    def test_build_scans_files_once_with_default_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "a.md", "x\n")
            _write(repo / "pkg" / "b.py", "x = 1\n")

            ctx = build_scan_context(repo, _config(repo))

            self.assertIsInstance(ctx, ScanContext)
            self.assertEqual(ctx.roots, (".",))
            self.assertEqual(ctx.files, ("a.md", "pkg/b.py"))
            self.assertEqual(list(ctx.files), sorted(ctx.files))

    def test_doc_claims_matches_adapter_and_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "doc.md", "See [design](missing.md).\n")

            ctx = build_scan_context(repo, _config(repo))
            claims = ctx.doc_claims()

            self.assertEqual(claims, tuple(extract_doc_claims(repo, ctx.files)))
            self.assertEqual([c.path for c in claims], ["missing.md"])
            # Second read returns the identical cached object (one adapter call).
            self.assertIs(ctx.doc_claims(), claims)

    def test_symbols_matches_adapter_and_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")

            ctx = build_scan_context(repo, _config(repo))
            facts = ctx.symbols()

            self.assertEqual(facts, extract_symbol_facts(repo, ctx.files))
            self.assertEqual([d.name for d in facts.definitions], ["handle"])
            # Second read returns the identical cached object (one adapter call).
            self.assertIs(ctx.symbols(), facts)

    def test_imports_matches_adapter_and_is_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "a.py", "import os\n")

            ctx = build_scan_context(repo, _config(repo))
            facts = ctx.imports()

            self.assertEqual(facts, extract_import_facts(repo, ctx.files))
            self.assertEqual([f.target for f in facts.imports], ["os"])
            self.assertIs(ctx.imports(), facts)

    def test_context_is_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            ctx = build_scan_context(repo, _config(repo))
            with self.assertRaises(Exception):
                ctx.files = ()  # type: ignore[misc]

    def test_no_policy_imports_an_adapter(self) -> None:
        # P3 §11 boundary guard (whole policy layer): no module under
        # codas.policies may import a codas.adapters.* module — policies receive
        # normalized facts via ScanContext. (codas.structure.index is NOT banned:
        # structure policies legitimately use the artifact index — only ecosystem
        # adapters are the boundary violation.) This is the interim guard; slice B2
        # turns it into a dogfooded Codas finding over Python import facts.
        package = policies_package.__name__  # "codas.policies"
        policy_dir = Path(policies_package.__file__).parent
        offenders: dict[str, list[str]] = {}
        for source_path in sorted(policy_dir.glob("*.py")):
            adapter_imports = [
                name
                for name in _imported_modules(source_path, package)
                if name.startswith("codas.adapters")
            ]
            if adapter_imports:
                offenders[source_path.name] = adapter_imports
        self.assertEqual(offenders, {}, f"policies must not import adapters: {offenders}")

    def test_import_guard_catches_bare_relative_adapter_import(self) -> None:
        # Regression: `from .. import adapters` has node.module=None, so the guard
        # must expand `base + leaf` to surface it as codas.adapters (not just base).
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "evil_policy.py"
            source.write_text("from .. import adapters\nfrom ..adapters import python\n")

            # `package` is the importing module's __package__ (e.g. codas.policies),
            # matching how the real guard resolves relative imports.
            imported = _imported_modules(source, "codas.policies")

            self.assertIn("codas.adapters", imported)
            self.assertIn("codas.adapters.python", imported)

    def test_stale_claim_imports_no_scan_index(self) -> None:
        # A1 guarantee: stale_claim receives files via ScanContext, so it no longer
        # imports the file-scan index directly either.
        package = stale_claim_module.__package__
        imported = _imported_modules(Path(stale_claim_module.__file__), package)
        self.assertNotIn("codas.structure.index", imported)


if __name__ == "__main__":
    unittest.main()
