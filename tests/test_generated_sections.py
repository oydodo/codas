from __future__ import annotations

import copy
import unittest
from pathlib import Path

from codas.adapters.wiki import extract_wiki_claims
from codas.app.check import run_check
from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.wiki import render_generated_overview
from codas.core.provenance import inventory_hash

GENERATED_DIR = ".codas/wiki/generated"
PAGE = ".codas/wiki/generated/governance.md"

MINI = {
    "units": [
        {"id": "u-b", "path": "src/b", "kind": "pkg", "owner": "Owner B"},
        {"id": "u-a", "path": ".codas", "kind": "gov", "owner": "Owner A"},
    ],
    "program": {
        "work_items": [{"id": "program:P1:x", "phase": "P1", "status": "completed"}]
    },
}


class RenderGeneratedOverviewTests(unittest.TestCase):
    def test_literal_content(self) -> None:
        # Non-circular: assert specific expected lines, independent of the render path.
        out = render_generated_overview(MINI, "sha256:test")
        self.assertIn("## Structure Units", out)
        self.assertIn("## Roadmap", out)
        self.assertIn("| `u-a` | `.codas` | gov | Owner A |", out)  # units id-sorted
        self.assertIn("| `u-b` | `src/b` | pkg | Owner B |", out)
        self.assertIn("| `program:P1:x` | P1 | completed |", out)
        self.assertIn("```atlas:claims", out)
        self.assertIn("source_inventory_hash: sha256:test", out)
        self.assertIn("unit: u-a -> .codas", out)
        self.assertIn("unit: u-b -> src/b", out)
        self.assertIn("roadmap: program:P1:x -> completed", out)
        # u-a sorts before u-b in the table AND the claims block.
        self.assertLess(out.index("unit: u-a"), out.index("unit: u-b"))

    def test_no_claim_creating_headings(self) -> None:
        out = render_generated_overview(MINI, "sha256:test").lower()
        for heading in ("## canonical sources", "## concepts", "## required synchronization"):
            self.assertNotIn(heading, out)
        self.assertNotIn("evidence:", out)

    def test_pure_and_deterministic(self) -> None:
        before = copy.deepcopy(MINI)
        first = render_generated_overview(MINI, "sha256:test")
        second = render_generated_overview(MINI, "sha256:test")
        self.assertEqual(first, second)
        self.assertEqual(MINI, before)  # input not mutated

    def test_cell_guard_rejects_table_breaker(self) -> None:
        bad = {"units": [{"id": "x|y", "path": "p", "kind": "k", "owner": "o"}]}
        with self.assertRaises(ValueError):
            render_generated_overview(bad, "sha256:test")

    def test_claim_token_guard_rejects_delimiter(self) -> None:
        bad = {"units": [{"id": "a->b", "path": "p", "kind": "k", "owner": "o"}]}
        with self.assertRaises(ValueError):
            render_generated_overview(bad, "sha256:test")

    def test_tolerates_no_program(self) -> None:
        out = render_generated_overview({"units": []}, "sha256:test")
        self.assertIn("## Roadmap", out)
        self.assertIn("source_inventory_hash: sha256:test", out)


class CommittedPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()
        self.page = self.repo / PAGE
        if not self.page.exists():
            self.skipTest("generated page not present (run `codas wiki --write`)")

    def test_page_produces_no_wiki_claims(self) -> None:
        claims = extract_wiki_claims(self.repo, (PAGE,))
        self.assertEqual(claims.claims, ())

    def test_committed_page_structure(self) -> None:
        # Structural, churn-robust: the committed page carries the required grounding
        # block + reflects current structure units. NOT a byte-freshness gate (the
        # embedded source_inventory_hash drifts on every src/test edit; freshness is
        # D3d generated_wiki_drift's job, a warning, not a hard test). Independent
        # render-logic validation lives in RenderGeneratedOverviewTests.
        text = self.page.read_text()
        self.assertIn("```atlas:claims", text)
        self.assertIn("source_inventory_hash: sha256:", text)
        self.assertIn("## Structure Units", text)
        # A real current unit must appear as a claim (units change rarely, via
        # structure.yml — regenerate then).
        self.assertIn("unit: codas-app -> src/codas/app", text)

    def test_rewrite_is_idempotent(self) -> None:
        # Rendering the current (generated-excluded) inventory twice is byte-identical
        # (the embedded hash is stable because the generated dir is excluded).
        inventory = run_inventory(self.repo, exclude_under=(GENERATED_DIR,))
        digest = inventory_hash(render_inventory_json(inventory))
        first = render_generated_overview(inventory, digest)
        second = render_generated_overview(inventory, digest)
        self.assertEqual(first, second)

    def test_committed_page_keeps_check_clean(self) -> None:
        report = run_check(self.repo)
        offending = [
            finding
            for finding in report.findings
            if any((ev.path or "") == PAGE for ev in finding.evidence)
        ]
        self.assertEqual(offending, [])


if __name__ == "__main__":
    unittest.main()
