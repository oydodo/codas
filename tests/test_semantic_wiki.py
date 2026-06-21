import json
import tempfile
import unittest
from pathlib import Path

from codas.adapters.semantic import SEMANTIC_WIKI_ROOT, extract_semantic_claims
from codas.app.inventory import run_inventory
from codas.config.loader import CodasConfig
from codas.facts.context import build_scan_context
from codas.policies.semantic_wiki import check_semantic_wiki


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# A sample package whose facts the semantic-wiki claims resolve against.
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

# A committed semantic-wiki page: a mix of resolving + non-resolving claims, a call-endpoint
# method node (in the tree but NOT in symbols), and a true tuple wrapped in a false concept.
_PAGE = """\
# pkg.a semantic notes

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


class SemanticWikiPolicyTests(unittest.TestCase):
    def _build(self, page=_PAGE):
        self.tmp = tempfile.TemporaryDirectory()
        repo = Path(self.tmp.name)
        _write(repo / "pkg" / "__init__.py", "")
        _write(repo / "pkg" / "a.py", _PKG)
        _write(repo / SEMANTIC_WIKI_ROOT / "page.md", page)
        self.addCleanup(self.tmp.cleanup)
        return repo

    def test_resolving_claims_warn_only_on_the_unresolved(self):
        repo = self._build()
        findings = check_semantic_wiki(_ctx(repo))
        # Exactly the two non-resolving claims warn; everything else resolves.
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
        repo = self._build()
        findings = check_semantic_wiki(_ctx(repo))
        self.assertTrue(findings)
        for f in findings:
            self.assertEqual(f.severity, "warning")  # open-world: never an error
            self.assertEqual(f.check_id, "semantic-wiki")
            self.assertIn("open-world", f.message)

    def test_concept_is_never_verified(self):
        # "implements a neural net -> pkg/a.py::::f": the tuple (f) resolves, so NO finding —
        # the false concept is irrelevant to the structural check (structure != meaning).
        repo = self._build()
        findings = check_semantic_wiki(_ctx(repo))
        self.assertNotIn("pkg/a.py::::f", [f.evidence[0].detail for f in findings])

    def test_call_endpoint_method_node_resolves(self):
        # `contains: pkg/a.py::C::m` cites a method node that is NOT in ctx.symbols() (only
        # top-level C/f/g are) but IS a call endpoint — the node-universe fix must resolve it,
        # not spuriously warn.
        repo = self._build()
        details = [f.evidence[0].detail for f in check_semantic_wiki(_ctx(repo))]
        self.assertNotIn("pkg/a.py::C::m", details)

    def test_package_dir_node_resolves(self):
        # `contains: pkg` cites a package/dir node (a path ancestor of pkg/a.py) — the
        # path-ancestor universe must resolve it, not spuriously warn.
        repo = self._build()
        details = [f.evidence[0].detail for f in check_semantic_wiki(_ctx(repo))]
        self.assertNotIn("pkg", details)

    def test_empty_wiki_no_findings(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(repo / "pkg" / "__init__.py", "")
            _write(repo / "pkg" / "a.py", _PKG)
            self.assertEqual(check_semantic_wiki(_ctx(repo)), [])

    def test_prose_is_out_of_the_claim_scans(self):
        # The committed page's prose path token must NOT become a doc-claim or wiki-claim
        # (SKIP_PREFIXES + extract_wiki_claims exclusion) — that is what keeps it out of the
        # inventory hash — while its structural claims DO surface via semantic_wiki_claims.
        repo = self._build()
        ctx = _ctx(repo)
        page = SEMANTIC_WIKI_ROOT + "/page.md"
        self.assertNotIn(page, {c.source for c in ctx.doc_claims()})
        self.assertNotIn(page, {c.source for c in ctx.wiki_claims().claims})
        self.assertIn(page, {c.source for c in ctx.semantic_wiki_claims().claims})


class HashIsolation(unittest.TestCase):
    def test_semantic_wiki_prose_edit_keeps_inventory_byte_identical(self):
        # A semantic-wiki page's PROSE must not enter the byte-identical inventory hash.
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
            page = repo / SEMANTIC_WIKI_ROOT / "p.md"
            _write(
                page,
                "# prose one\nsee pkg/a.py for details\n```atlas:claims\ncontains: pkg/a.py\n```\n",
            )
            h1 = json.dumps(run_inventory(repo), sort_keys=True)
            page.write_text(
                "# COMPLETELY DIFFERENT prose two\nnow mentions pkg/b.py and pkg/c.py\n"
                "```atlas:claims\ncontains: pkg/a.py\n```\n",
                encoding="utf-8",
            )
            h2 = json.dumps(run_inventory(repo), sort_keys=True)
            self.assertEqual(h1, h2)  # prose changed, inventory identical


class SemanticAdapterFilesParamTests(unittest.TestCase):
    def test_files_param_uses_tracked_list_not_rglob(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(repo / SEMANTIC_WIKI_ROOT / "tracked.md", "```atlas:claims\ncontains: pkg/a.py\n```\n")
            _write(repo / SEMANTIC_WIKI_ROOT / "untracked.md", "```atlas:claims\ncontains: pkg/b.py\n```\n")
            # files given = only the tracked one is parsed (untracked.md is invisible)
            tracked = (SEMANTIC_WIKI_ROOT + "/tracked.md",)
            claims = extract_semantic_claims(repo, SEMANTIC_WIKI_ROOT, tracked).claims
            self.assertEqual([c.subject for c in claims], ["pkg/a.py"])


if __name__ == "__main__":
    unittest.main()
