"""Atlas code-wiki anchor verifier (W1, all-open).

Pins the anchor grammar (robust, position-stripped), the all-open verifier (non-resolving
anchor = WARNING never error), and the hash isolation (code-wiki prose stays out of the
byte-identical inventory). The code->doc drift catch: a renamed anchored symbol warns.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codas.adapters.wiki import _parse_anchor_symbol, extract_code_anchor_claims
from codas.app.check import run_check
from codas.app.inventory import run_inventory
from codas.config.loader import load_codas_config
from codas.facts.context import ScanContext
from codas.policies.code_anchor import check_code_anchor

REPO = Path(__file__).resolve().parents[1]


class ParseAnchorSymbol(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            _parse_anchor_symbol(" concept -> src/x.py:foo"),
            ("concept", "src/x.py", "foo"),
        )

    def test_concept_with_arrow(self):
        # split concept/target on the LAST ' -> '
        self.assertEqual(
            _parse_anchor_symbol("a -> b -> src/x.py:foo"),
            ("a -> b", "src/x.py", "foo"),
        )

    def test_backslash_and_dot_slash_normalized(self):
        self.assertEqual(
            _parse_anchor_symbol("c -> .\\src\\x.py:foo"),
            ("c", "src/x.py", "foo"),
        )

    def test_malformed_returns_none(self):
        for bad in ["no arrow src/x.py:foo", "c -> noColonHere", "c -> :foo", "c -> src/x.py:", " -> src/x.py:foo", "c -> ../escape.py:foo"]:
            self.assertIsNone(_parse_anchor_symbol(bad), bad)


class ExtractCodeAnchorClaims(unittest.TestCase):
    def _write(self, body: str):
        d = tempfile.mkdtemp()
        repo = Path(d)
        (repo / ".codas" / "wiki" / "code").mkdir(parents=True)
        (repo / ".codas" / "wiki" / "code" / "p.md").write_text(body)
        return extract_code_anchor_claims(repo, (".codas/wiki/code/p.md",)), repo

    def test_reads_only_inside_fence(self):
        body = (
            "anchor_symbol: outside -> src/a.py:x\n"   # outside fence -> ignored
            "```atlas:claims\n"
            "anchor_symbol: inside -> src/b.py:y\n"
            "```\n"
            "anchor_symbol: after -> src/c.py:z\n"     # after fence -> ignored
        )
        claims, _ = self._write(body)
        self.assertEqual([(c.concept, c.path, c.name) for c in claims.claims],
                         [("inside", "src/b.py", "y")])

    def test_malformed_lines_skipped_not_crash(self):
        body = "```atlas:claims\nanchor_symbol: bad line no arrow\nanchor_symbol: ok -> src/a.py:f\n```\n"
        claims, _ = self._write(body)
        self.assertEqual([(c.path, c.name) for c in claims.claims], [("src/a.py", "f")])


class AllOpenVerifier(unittest.TestCase):
    def _ctx_with(self, anchors):
        ctx = ScanContext(repo=Path("/x"), config=None, roots=(), files=())  # type: ignore[arg-type]
        from codas.adapters.wiki import CodeAnchorClaim, CodeAnchorClaims
        from codas.adapters.python import SymbolFact, SymbolFacts

        ctx._cache["code_anchor_claims"] = CodeAnchorClaims(claims=tuple(anchors), skipped=())
        ctx._cache["symbols"] = SymbolFacts(
            definitions=(SymbolFact(module="src/a.py", name="present", kind="function", line=1),),
            skipped=(),
        )
        return ctx

    def _anchor(self, path, name, line=3):
        from codas.adapters.wiki import CodeAnchorClaim
        return CodeAnchorClaim(source=".codas/wiki/code/p.md", line=line, concept="c", path=path, name=name)

    def test_resolving_anchor_clean(self):
        ctx = self._ctx_with([self._anchor("src/a.py", "present")])
        self.assertEqual(check_code_anchor(ctx), [])

    def test_missing_anchor_is_warning_not_error(self):
        ctx = self._ctx_with([self._anchor("src/a.py", "gone")])
        findings = check_code_anchor(ctx)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warning")  # ALL-OPEN: never error
        self.assertEqual(findings[0].check_id, "code-anchor")
        self.assertIn("lower bound", findings[0].message)  # the open-world caveat

    def test_no_anchors_no_findings(self):
        ctx = self._ctx_with([])
        self.assertEqual(check_code_anchor(ctx), [])


class HashIsolation(unittest.TestCase):
    def test_code_wiki_prose_edit_keeps_inventory_byte_identical(self):
        # A committed code-wiki page's PROSE must not enter the byte-identical hash.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".codas").mkdir()
            (repo / ".codas" / "config.yml").write_text("version: 1\n")
            (repo / ".codas" / "structure.yml").write_text(
                "version: 1\nkind: structure_map\nunits:\n  root:\n    path: .\n    kind: dir\n    owner: x\n    purpose: root\n    canonical_placement: root\n"
            )
            (repo / ".codas" / "wiki" / "code").mkdir(parents=True)
            page = repo / ".codas" / "wiki" / "code" / "p.md"
            page.write_text("# prose one\nsee src/a.py for details\n```atlas:claims\nanchor_symbol: c -> src/a.py:f\n```\n")
            h1 = json.dumps(run_inventory(repo), sort_keys=True)
            page.write_text("# COMPLETELY DIFFERENT prose two\nnow mentions src/b.py and src/c.py\n```atlas:claims\nanchor_symbol: c -> src/a.py:f\n```\n")
            h2 = json.dumps(run_inventory(repo), sort_keys=True)
            self.assertEqual(h1, h2)  # prose changed, inventory identical


class RepoLevel(unittest.TestCase):
    def test_committed_openworld_page_anchors_resolve(self):
        report = run_check(REPO)
        self.assertNotIn("code-anchor", [f.check_id for f in report.findings])

    def test_code_anchor_claims_not_in_inventory(self):
        inventory = run_inventory(REPO)
        self.assertNotIn("code_anchor_claims", inventory)
        self.assertNotIn("code_anchors", inventory)


if __name__ == "__main__":
    unittest.main()
