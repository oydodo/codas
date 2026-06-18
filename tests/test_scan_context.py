from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import codas.policies.stale_claim as stale_claim_module
from codas.adapters.markdown import extract_doc_claims
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

    def test_context_is_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            ctx = build_scan_context(repo, _config(repo))
            with self.assertRaises(Exception):
                ctx.files = ()  # type: ignore[misc]

    def test_stale_claim_imports_no_adapter(self) -> None:
        # P3 boundary guard (scoped to the migrated policy): the policy module must
        # not import an ecosystem adapter or the file-scan index directly — it
        # receives normalized facts via ScanContext. The general policy-layer ban
        # is the dependency-direction policy (slice B2).
        package = stale_claim_module.__package__  # "codas.policies"
        source = Path(stale_claim_module.__file__).read_text()
        imported: list[str] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                imported.append(_absolute_module(node, package))
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)

        offenders = [
            name
            for name in imported
            if name.startswith("codas.adapters") or name == "codas.structure.index"
        ]
        self.assertEqual(offenders, [], f"stale_claim must not import {offenders}")


if __name__ == "__main__":
    unittest.main()
