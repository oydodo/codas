"""Atlas code-wiki structural-claim verifier (W5-unified, all-open).

Pins the unified defines/calls/contains grammar (robust, position-stripped), the all-open
verifier (a non-resolving claim = WARNING never error), the node universe (top-level symbols
∪ call-endpoint method nodes ∪ path/package ancestors), and the hash isolation (code-wiki
prose stays out of the byte-identical inventory). The code->doc drift catch: a renamed
claimed symbol/edge warns. (Folds in the former separate semantic_wiki tests — W5.)
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codas.adapters.semantic import extract_semantic_claims
from codas.app.check import run_check
from codas.app.inventory import run_inventory
from codas.config.loader import CodasConfig
from codas.facts.context import build_scan_context
from codas.policies.code_anchor import check_code_anchor

REPO = Path(__file__).resolve().parents[1]
CODE_ROOT = ".codas/wiki/code"  # the committed code-wiki root (config wiki.path + /code)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# A sample package whose facts the code-wiki claims resolve against.
_PKG = """\
def f():
    g()


def g():
    pass


class C:
    def m(self):
        self.n()

    def n(self):
        pass
"""

# A committed code-wiki page: a mix of resolving + non-resolving claims, a call-endpoint
# method node (in the tree but NOT in symbols), and a true tuple wrapped in a false concept.
_PAGE = """\
# pkg.a code-wiki notes

Prose describing the module. A path-shaped token `pkg/a.py` here must NOT become a doc-claim
(the prose is excluded from the claim scans).

```atlas:claims
defines: the entry function -> pkg/a.py::::f
calls: pkg/a.py::::f -> pkg/a.py::::g
contains: pkg/a.py
contains: pkg
contains: pkg/a.py::C::m
defines: implements a neural net -> pkg/a.py::::f
defines: missing thing -> pkg/a.py::::does_not_exist
calls: pkg/a.py::::f -> pkg/a.py::::does_not_exist
```
"""


def _ctx(repo: Path):
    return build_scan_context(repo, CodasConfig(path=repo / ".codas" / "config.yml", raw={}))


class CodeWikiPolicyTests(unittest.TestCase):
    def _build(self, page=_PAGE):
        self.tmp = tempfile.TemporaryDirectory()
        repo = Path(self.tmp.name)
        _write(repo / "pkg" / "__init__.py", "")
        _write(repo / "pkg" / "a.py", _PKG)
        _write(repo / CODE_ROOT / "page.md", page)
        self.addCleanup(self.tmp.cleanup)
        return repo

    def test_resolving_claims_warn_only_on_the_unresolved(self):
        findings = check_code_anchor(_ctx(self._build()))
        details = sorted(f.evidence[0].detail for f in findings)
        self.assertEqual(
            details,
            sorted(
                [
                    "pkg/a.py::::f -> pkg/a.py::::does_not_exist",
                    "pkg/a.py::::does_not_exist",
                ]
            ),
        )

    def test_all_open_warning_never_error(self):
        findings = check_code_anchor(_ctx(self._build()))
        self.assertTrue(findings)
        for f in findings:
            self.assertEqual(f.severity, "warning")  # open-world: never an error
            self.assertEqual(f.check_id, "code-anchor")
            self.assertIn("open-world", f.message)

    def test_concept_is_never_verified(self):
        # "implements a neural net -> pkg/a.py::::f": the tuple (f) resolves, so NO finding —
        # the false concept is irrelevant to the structural check (structure != meaning).
        findings = check_code_anchor(_ctx(self._build()))
        self.assertNotIn("pkg/a.py::::f", [f.evidence[0].detail for f in findings])

    def test_call_endpoint_method_node_resolves(self):
        # `contains: pkg/a.py::C::m` cites a method node NOT in ctx.symbols() (only top-level
        # C/f/g are) but IS a call endpoint — the node-universe must resolve it, not warn.
        details = [f.evidence[0].detail for f in check_code_anchor(_ctx(self._build()))]
        self.assertNotIn("pkg/a.py::C::m", details)

    def test_package_dir_node_resolves(self):
        # `contains: pkg` cites a package/dir node (a path ancestor of pkg/a.py) — the
        # path-ancestor universe must resolve it, not spuriously warn.
        details = [f.evidence[0].detail for f in check_code_anchor(_ctx(self._build()))]
        self.assertNotIn("pkg", details)

    def test_empty_wiki_no_findings(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "a.py", _PKG)
            self.assertEqual(check_code_anchor(_ctx(repo)), [])

    def test_prose_is_out_of_the_claim_scans(self):
        # The page's prose path token must NOT become a doc-claim or wiki-claim (SKIP_PREFIXES
        # + extract_wiki_claims exclusion) — that keeps it out of the inventory hash — while
        # its structural claims DO surface via code_anchor_claims.
        ctx = _ctx(self._build())
        page = CODE_ROOT + "/page.md"
        self.assertNotIn(page, {c.source for c in ctx.doc_claims()})
        self.assertNotIn(page, {c.source for c in ctx.wiki_claims().claims})
        self.assertIn(page, {c.source for c in ctx.code_anchor_claims().claims})


class ParserRobustness(unittest.TestCase):
    def _claims(self, body: str):
        d = tempfile.mkdtemp()
        repo = Path(d)
        _write(repo / CODE_ROOT / "p.md", body)
        return extract_semantic_claims(repo, CODE_ROOT, (CODE_ROOT + "/p.md",)).claims

    def test_reads_only_inside_fence(self):
        body = (
            "defines: outside -> src/a.py::::x\n"  # outside fence -> ignored
            "```atlas:claims\n"
            "defines: inside -> src/b.py::::y\n"
            "```\n"
            "defines: after -> src/c.py::::z\n"  # after fence -> ignored
        )
        claims = self._claims(body)
        self.assertEqual(
            [(c.kind, c.concept, c.subject) for c in claims],
            [("defines", "inside", "src/b.py::::y")],
        )

    def test_malformed_lines_skipped_not_crash(self):
        body = "```atlas:claims\ndefines: bad no arrow\ndefines: ok -> src/a.py::::f\n```\n"
        claims = self._claims(body)
        self.assertEqual([c.subject for c in claims], ["src/a.py::::f"])

    def test_files_param_uses_tracked_list_not_rglob(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(repo / CODE_ROOT / "tracked.md", "```atlas:claims\ncontains: pkg/a.py\n```\n")
            _write(repo / CODE_ROOT / "untracked.md", "```atlas:claims\ncontains: pkg/b.py\n```\n")
            tracked = (CODE_ROOT + "/tracked.md",)
            claims = extract_semantic_claims(repo, CODE_ROOT, tracked).claims
            self.assertEqual([c.subject for c in claims], ["pkg/a.py"])


class HashIsolation(unittest.TestCase):
    def test_code_wiki_prose_edit_keeps_inventory_byte_identical(self):
        # A committed code-wiki page's PROSE must not enter the byte-identical hash.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(repo / ".codas" / "config.yml", "version: 1\n")
            _write(
                repo / ".codas" / "structure.yml",
                "version: 1\nkind: structure_map\nunits:\n  root:\n    path: .\n"
                "    kind: dir\n    owner: x\n    purpose: root\n    canonical_placement: root\n",
            )
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "a.py", _PKG)
            page = repo / CODE_ROOT / "p.md"
            _write(page, "# prose one\nsee pkg/a.py\n```atlas:claims\ncontains: pkg/a.py\n```\n")
            h1 = json.dumps(run_inventory(repo), sort_keys=True)
            page.write_text(
                "# DIFFERENT prose two\nmentions pkg/b.py and pkg/c.py\n"
                "```atlas:claims\ncontains: pkg/a.py\n```\n",
                encoding="utf-8",
            )
            h2 = json.dumps(run_inventory(repo), sort_keys=True)
            self.assertEqual(h1, h2)  # prose changed, inventory identical


class RepoLevel(unittest.TestCase):
    def test_committed_openworld_page_claims_resolve(self):
        report = run_check(REPO)
        self.assertNotIn("code-anchor", [f.check_id for f in report.findings])

    def test_code_anchor_claims_not_in_inventory(self):
        inventory = run_inventory(REPO)
        self.assertNotIn("code_anchor_claims", inventory)
        self.assertNotIn("code_anchors", inventory)


if __name__ == "__main__":
    unittest.main()
