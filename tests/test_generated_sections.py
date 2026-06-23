from __future__ import annotations

import copy
import unittest
from pathlib import Path

from codas.adapters.wiki import extract_wiki_claims
from codas.app.check import run_check
from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.wiki import render_generated_overview

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
        out = render_generated_overview(MINI)
        self.assertIn("## Structure Units", out)
        self.assertIn("## Roadmap", out)
        self.assertIn("| `u-a` | `.codas` | gov | Owner A |", out)  # units id-sorted
        self.assertIn("| `u-b` | `src/b` | pkg | Owner B |", out)
        self.assertIn("| `program:P1:x` | P1 | completed |", out)
        self.assertIn("```atlas:claims", out)
        # No embedded freshness hash: the claims block opens straight into the claims.
        self.assertNotIn("source_inventory_hash", out)
        self.assertIn("unit: u-a -> .codas", out)
        self.assertIn("unit: u-b -> src/b", out)
        self.assertIn("roadmap: program:P1:x -> completed", out)
        # u-a sorts before u-b in the table AND the claims block.
        self.assertLess(out.index("unit: u-a"), out.index("unit: u-b"))

    def test_no_claim_creating_headings(self) -> None:
        out = render_generated_overview(MINI).lower()
        for heading in ("## canonical sources", "## concepts", "## required synchronization"):
            self.assertNotIn(heading, out)
        self.assertNotIn("evidence:", out)

    def test_pure_and_deterministic(self) -> None:
        before = copy.deepcopy(MINI)
        first = render_generated_overview(MINI)
        second = render_generated_overview(MINI)
        self.assertEqual(first, second)
        self.assertEqual(MINI, before)  # input not mutated

    def test_cell_guard_rejects_table_breaker(self) -> None:
        bad = {"units": [{"id": "x|y", "path": "p", "kind": "k", "owner": "o"}]}
        with self.assertRaises(ValueError):
            render_generated_overview(bad)

    def test_claim_token_guard_rejects_delimiter(self) -> None:
        bad = {"units": [{"id": "a->b", "path": "p", "kind": "k", "owner": "o"}]}
        with self.assertRaises(ValueError):
            render_generated_overview(bad)

    def test_tolerates_no_program(self) -> None:
        out = render_generated_overview({"units": []})
        self.assertIn("## Roadmap", out)
        self.assertNotIn("source_inventory_hash", out)


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
        # block + reflects current structure units. Freshness is NOT a hard test here;
        # it rides in the rendered bytes (codas wiki --verify byte-compare). The page
        # carries NO embedded source_inventory_hash. Independent render-logic validation
        # lives in RenderGeneratedOverviewTests.
        text = self.page.read_text()
        self.assertIn("```atlas:claims", text)
        self.assertNotIn("source_inventory_hash", text)
        self.assertIn("## Structure Units", text)
        # A real current unit must appear as a claim (units change rarely, via
        # structure.yml — regenerate then).
        self.assertIn("unit: codas-app -> src/codas/app", text)

    def test_render_is_deterministic(self) -> None:
        # Run-twice determinism: rendering the current (generated-excluded) inventory
        # twice is byte-identical — the freshness signal the --verify byte-compare relies
        # on, with no embedded hash needed.
        inventory = run_inventory(self.repo, exclude_under=(GENERATED_DIR,))
        first = render_generated_overview(inventory)
        second = render_generated_overview(inventory)
        self.assertEqual(first, second)

    def test_inventory_render_is_deterministic(self) -> None:
        # The determinism the page freshness rests on: building the inventory twice
        # yields byte-identical canonical JSON (canonical serialization is preserved even
        # though the freshness hash is gone).
        first = render_inventory_json(run_inventory(self.repo, exclude_under=(GENERATED_DIR,)))
        second = render_inventory_json(run_inventory(self.repo, exclude_under=(GENERATED_DIR,)))
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
