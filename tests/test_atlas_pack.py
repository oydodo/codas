from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.wiki import build_atlas_pack, project_atlas_pack
from codas.cli import main
from codas.core.provenance import inventory_hash

GENERATED = ".codas/wiki/generated"

# Hand-crafted minimal inventory exercising every projection rule (codex SHOULD):
# product-path scoping, external-import drop, exists filter, deterministic sort.
MINI = {
    "units": [
        {"id": "u2", "path": "b", "kind": "k", "owner": "o2"},
        {"id": "u1", "path": "a", "kind": "k", "owner": "o1"},
    ],
    "symbols": {
        "definitions": [
            {"module": "src/codas/x.py", "name": "f", "kind": "function", "line": 3},
            {"module": "tests/t.py", "name": "g", "kind": "function", "line": 1},
        ]
    },
    "imports": {
        "edges": [
            {"module": "src/codas/x.py", "target": "codas.y",
             "target_path": "src/codas/y.py", "line": 1},
            {"module": "src/codas/x.py", "target": "os",
             "target_path": None, "line": 2},
            {"module": ".trellis/scripts/z.py", "target": "scripts.w",
             "target_path": ".trellis/scripts/w.py", "line": 1},
        ]
    },
    "wiki_claims": {
        "claims": [
            {"source": "s", "concept": "c", "kind": "concept_page",
             "path": "p.md", "exists": True},
            {"source": "s2", "concept": "c2", "kind": "evidence",
             "path": "e.py", "exists": True},
            {"source": "s3", "concept": "c3", "kind": "evidence",
             "path": "miss.py", "exists": False},
        ]
    },
    "program": {"work_items": [{"id": "P1", "phase": "P1", "status": "done"}]},
}


class ProjectAtlasPackTests(unittest.TestCase):
    def test_projection_logic(self) -> None:
        pack = project_atlas_pack(MINI)
        self.assertEqual(
            pack["dependency_graph"],
            [{"module": "src/codas/x.py", "target": "codas.y",
              "target_path": "src/codas/y.py"}],  # external `os` dropped
        )
        self.assertEqual(
            pack["symbol_index"],
            [{"module": "src/codas/x.py", "name": "f", "kind": "function", "line": 3}],
        )  # tests/t.py is not product-scoped
        self.assertEqual([u["id"] for u in pack["ownership"]], ["u1", "u2"])  # id sort
        self.assertEqual(
            pack["concept_index"],
            [{"concept": "c", "path": "p.md", "exists": True}],
        )
        self.assertEqual(
            [(e["source"], e["kind"]) for e in pack["verified_evidence"]],
            [("s", "concept_page"), ("s2", "evidence")],  # exists=False dropped, sorted
        )
        self.assertEqual(pack["roadmap"], [{"id": "P1", "phase": "P1", "status": "done"}])
        self.assertIn("VERIFIED GOVERNANCE FACTS", pack["preamble"])

    def test_pure_and_deterministic(self) -> None:
        before = copy.deepcopy(MINI)
        first = project_atlas_pack(MINI)
        second = project_atlas_pack(MINI)
        self.assertEqual(first, second)
        self.assertEqual(MINI, before)  # input not mutated

    def test_tolerates_minimal_inventory(self) -> None:
        pack = project_atlas_pack({"units": []})
        self.assertEqual(pack["dependency_graph"], [])
        self.assertEqual(pack["roadmap"], [])
        self.assertEqual(pack["concept_index"], [])


class BuildAtlasPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()

    def test_derived_view_invariant(self) -> None:
        pack = build_atlas_pack(self.repo)
        self.assertIn("source_inventory_hash", pack)
        rebuilt = project_atlas_pack(run_inventory(self.repo, exclude_under=(GENERATED,)))
        without_hash = {k: v for k, v in pack.items() if k != "source_inventory_hash"}
        self.assertEqual(without_hash, rebuilt)

    def test_source_hash_is_generated_excluded(self) -> None:
        # This test's "exclusion is a no-op" assumption holds only while no generated
        # dir exists. Assert that precondition LOUDLY so D3b/c (which commits pages
        # under .codas/wiki/generated/) fails here and forces a real divergence test,
        # rather than this silently passing on a now-meaningful exclusion (codex SHOULD).
        self.assertFalse(
            (self.repo / ".codas" / "wiki" / "generated").exists(),
            "generated wiki pages exist -> restructure this test to assert the "
            "source_inventory_hash DIVERGES from the full inventory hash",
        )
        pack = build_atlas_pack(self.repo)
        expected = inventory_hash(render_inventory_json(run_inventory(self.repo)))
        self.assertEqual(pack["source_inventory_hash"], expected)


class ExcludeUnderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path.cwd()

    def test_generated_exclusion_is_noop_today(self) -> None:
        self.assertEqual(
            run_inventory(self.repo, exclude_under=(GENERATED,)),
            run_inventory(self.repo),
        )

    def test_excluding_existing_dir_changes_inventory(self) -> None:
        # Proves the filter actually reaches the fact tables.
        self.assertNotEqual(
            run_inventory(self.repo, exclude_under=("src/codas/app",)),
            run_inventory(self.repo),
        )

    def test_default_path_byte_identical(self) -> None:
        a = render_inventory_json(run_inventory(self.repo))
        b = render_inventory_json(run_inventory(self.repo))
        self.assertEqual(a, b)


class WikiCliTests(unittest.TestCase):
    def test_emit_pack_prints_json(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["wiki", str(Path.cwd()), "--emit-pack"])
        self.assertEqual(code, 0)
        pack = json.loads(buffer.getvalue())
        for key in ("preamble", "dependency_graph", "symbol_index", "ownership",
                    "concept_index", "verified_evidence", "roadmap",
                    "source_inventory_hash"):
            self.assertIn(key, pack)


if __name__ == "__main__":
    unittest.main()
