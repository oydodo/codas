import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.adapters.semantic import (
    _KINDS,
    StructuralClaim,
    extract_semantic_claims,
)
from codas.app.calibrate import (
    CONTRADICTED,
    SEMANTIC,
    STRUCTURE_CONFIRMED,
    UNCONFIRMED,
    build_feed,
    run_calibrate,
    tier,
)
from codas.cli import main
from codas.facts.openworld import WORLD_BY_FAMILY, world_of
from codas.structure.index import discover_files


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _claim(kind, subject, object="", concept=""):
    return StructuralClaim(
        source="c.md", line=1, kind=kind, subject=subject, object=object, concept=concept
    )


class WorldMapTests(unittest.TestCase):
    def test_open_and_closed_families(self):
        for fam in ("symbols", "imports", "calls", "contains"):
            self.assertEqual(world_of(fam), "open")
        for fam in ("units", "tasks", "work_items", "documents"):
            self.assertEqual(world_of(fam), "closed")

    def test_unknown_family_is_none(self):
        self.assertIsNone(world_of("nope"))
        # never derive closed-world from absence
        self.assertNotIn("nope", WORLD_BY_FAMILY)


class TierTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {"a.py::::f", "a.py::::g", "a.py", "a.py::C::m"}
        self.calls = {"a.py::::f": {"a.py::::g"}}

    def test_contains_present_is_structure_confirmed(self):
        self.assertEqual(tier(_claim("contains", "a.py::::f"), self.nodes, self.calls),
                         STRUCTURE_CONFIRMED)
        self.assertEqual(tier(_claim("contains", "a.py"), self.nodes, self.calls),
                         STRUCTURE_CONFIRMED)

    def test_contains_absent_is_unconfirmed_never_false(self):
        # open-world: a missing node is UNKNOWN, never CONTRADICTED
        v = tier(_claim("contains", "a.py::::missing"), self.nodes, self.calls)
        self.assertEqual(v, UNCONFIRMED)
        self.assertNotEqual(v, CONTRADICTED)

    def test_defines_present_absent(self):
        self.assertEqual(tier(_claim("defines", "a.py::C::m", concept="x"), self.nodes, self.calls),
                         STRUCTURE_CONFIRMED)
        self.assertEqual(tier(_claim("defines", "a.py::::zzz", concept="x"), self.nodes, self.calls),
                         UNCONFIRMED)

    def test_calls_present_absent(self):
        self.assertEqual(tier(_claim("calls", "a.py::::f", "a.py::::g"), self.nodes, self.calls),
                         STRUCTURE_CONFIRMED)
        # edge absent -> UNCONFIRMED (calls is open-world)
        self.assertEqual(tier(_claim("calls", "a.py::::f", "a.py::::zzz"), self.nodes, self.calls),
                         UNCONFIRMED)
        # subject with no out-edges at all
        self.assertEqual(tier(_claim("calls", "a.py::::g", "a.py::::f"), self.nodes, self.calls),
                         UNCONFIRMED)

    def test_unknown_kind_is_semantic(self):
        self.assertEqual(tier(_claim("implements", "a.py::::f"), self.nodes, self.calls),
                         SEMANTIC)

    def test_contradicted_unreachable_for_all_kinds(self):
        # v0 has no closed-world claim kind, so an ABSENT match never yields CONTRADICTED.
        for kind in _KINDS:
            v = tier(_claim(kind, "z.py::::absent", "z.py::::absent2"), self.nodes, self.calls)
            self.assertIn(v, (UNCONFIRMED, SEMANTIC))
            self.assertNotEqual(v, CONTRADICTED)

    def test_concept_cannot_launder_the_tier(self):
        # The W3 iron rule: a structural match confirms the TUPLE, never the concept. The
        # LLM cannot change the tier by choosing its prose — same tuple, any concept, same
        # tier; and a true tuple wrapped in a false concept is STILL only STRUCTURE_CONFIRMED
        # (the concept is never confirmed).
        true_prose = _claim("defines", "a.py::C::m", concept="formats the report")
        false_prose = _claim("defines", "a.py::C::m", concept="trains a neural net")
        self.assertEqual(tier(true_prose, self.nodes, self.calls),
                         tier(false_prose, self.nodes, self.calls))
        self.assertEqual(tier(false_prose, self.nodes, self.calls), STRUCTURE_CONFIRMED)


class SemanticAdapterTests(unittest.TestCase):
    def test_parses_kinds_and_skips_malformed(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(
                repo / ".codas" / "cache" / "semantic" / "p.md",
                "prose\n"
                "```atlas:claims\n"
                "defines: builds X -> a/b.py::::f\n"
                "calls: a/b.py::::f -> a/b.py::::g\n"
                "contains: a/b.py\n"
                "defines: missing arrow a/b.py::::f\n"   # malformed -> skipped
                "calls: a/b.py::::f\n"                    # malformed (no object) -> skipped
                "junk line\n"
                "```\n"
                "not in block: a/b.py::::z\n",            # outside fence -> ignored
            )
            claims = extract_semantic_claims(repo).claims
            got = {(c.kind, c.subject, c.object, c.concept) for c in claims}
            self.assertEqual(
                got,
                {
                    ("defines", "a/b.py::::f", "", "builds X"),
                    ("calls", "a/b.py::::f", "a/b.py::::g", ""),
                    ("contains", "a/b.py", "", ""),
                },
            )

    def test_no_corpus_dir_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            result = extract_semantic_claims(Path(d))
            self.assertEqual(result.claims, ())
            self.assertEqual(result.skipped, ())

    def test_rejects_bad_node_ids(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(
                repo / ".codas" / "cache" / "semantic" / "p.md",
                "```atlas:claims\n"
                "contains: a/b.py::Cls\n"          # 1 '::' -> malformed
                "contains: ../escape.py\n"          # path escape -> rejected
                "contains: a/b.py::C::m\n"           # valid
                "```\n",
            )
            claims = extract_semantic_claims(repo).claims
            self.assertEqual([c.subject for c in claims], ["a/b.py::C::m"])


class CorpusOutOfHashTests(unittest.TestCase):
    def test_gitignored_corpus_is_not_discovered_but_adapter_reads_it(self):
        # The corpus-out-of-hash guarantee: a file under the gitignored `.codas/cache/` is
        # never DISCOVERED into the scanned file set (so it cannot enter the inventory hash
        # or any claim adapter), YET the offline semantic adapter reads it directly off disk.
        # Requires a git repo for the gitignore exclusion (the design's stated assumption).
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            _write(repo / ".gitignore", ".codas/cache/\n")
            _write(repo / "pkg" / "a.py", "def f():\n    return 1\n")
            _write(
                repo / ".codas" / "cache" / "semantic" / "p.md",
                "```atlas:claims\ncontains: pkg/a.py\n```\n",
            )
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

            files = discover_files(repo, (".",))
            self.assertIn("pkg/a.py", files)
            self.assertNotIn(".codas/cache/semantic/p.md", files)  # invisible to discovery

            # ...yet the offline adapter DOES read it directly
            claims = extract_semantic_claims(repo).claims
            self.assertEqual([c.subject for c in claims], ["pkg/a.py"])

    def test_corpus_excluded_in_non_git_walk_fallback(self):
        # The exclusion must hold WITHOUT git too: .codas/cache is pruned in the os.walk
        # fallback (_IGNORE_PATHS), so a non-git repo's corpus is still never discovered.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)  # deliberately NOT a git repo -> walk fallback
            _write(repo / "pkg" / "a.py", "x = 1\n")
            _write(
                repo / ".codas" / "cache" / "semantic" / "p.md",
                "```atlas:claims\ncontains: pkg/a.py\n```\n",
            )
            files = discover_files(repo, (".",))
            self.assertIn("pkg/a.py", files)
            self.assertNotIn(".codas/cache/semantic/p.md", files)
            self.assertEqual(
                [c.subject for c in extract_semantic_claims(repo).claims], ["pkg/a.py"]
            )


class CalibrateEndToEndTests(unittest.TestCase):
    # Exercises calibrate() through run_calibrate on the live dogfood repo (which has a real
    # knowledge tree), with a transient corpus under the gitignored cache, removed after.
    def setUp(self):
        self.repo = Path.cwd()
        self.corpus = self.repo / ".codas" / "cache" / "semantic" / "_test_e2e.md"

    def tearDown(self):
        if self.corpus.exists():
            self.corpus.unlink()

    def test_calibrate_tiers_present_and_absent_and_is_deterministic(self):
        _write(
            self.corpus,
            "```atlas:claims\n"
            "contains: src/codas/app/wiki.py::::build_atlas_tree\n"
            "defines: builds the tree -> src/codas/app/wiki.py::::project_atlas_tree\n"
            "calls: src/codas/app/wiki.py::::build_atlas_tree -> "
            "src/codas/app/wiki.py::::project_atlas_tree\n"
            "contains: src/codas/app/wiki.py::::does_not_exist_zzz\n"
            "```\n",
        )
        a = json.dumps(run_calibrate(self.repo), sort_keys=True)
        b = json.dumps(run_calibrate(self.repo), sort_keys=True)
        self.assertEqual(a, b)  # calibrate() is deterministic
        rows = json.loads(a)["calibration"]
        by = {(r["kind"], r["subject"], r["object"]): r["tier"] for r in rows}
        self.assertEqual(
            by[("contains", "src/codas/app/wiki.py::::build_atlas_tree", "")],
            STRUCTURE_CONFIRMED,
        )
        self.assertEqual(
            by[("defines", "src/codas/app/wiki.py::::project_atlas_tree", "")],
            STRUCTURE_CONFIRMED,
        )
        self.assertEqual(
            by[
                (
                    "calls",
                    "src/codas/app/wiki.py::::build_atlas_tree",
                    "src/codas/app/wiki.py::::project_atlas_tree",
                )
            ],
            STRUCTURE_CONFIRMED,
        )
        self.assertEqual(
            by[("contains", "src/codas/app/wiki.py::::does_not_exist_zzz", "")],
            UNCONFIRMED,
        )


class FeedAndCliTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()

    def test_build_feed_shape_and_deterministic(self):
        a = json.dumps(build_feed(self.repo), indent=2, sort_keys=True)
        b = json.dumps(build_feed(self.repo), indent=2, sort_keys=True)
        self.assertEqual(a, b)
        feed = json.loads(a)
        self.assertEqual(feed["schema"], "codas.semantic_feed/v1")
        self.assertIn("instructions", feed)
        self.assertTrue(feed["open_world"]["is_lower_bound"])
        self.assertEqual(feed["knowledge_tree"]["schema"], "codas.knowledge_tree/v1")

    def test_emit_feed_cli(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["wiki", str(self.repo), "--emit-feed"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buffer.getvalue())["schema"], "codas.semantic_feed/v1")

    def test_calibrate_cli(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["wiki", str(self.repo), "--calibrate"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["schema"], "codas.semantic_calibration/v1")
        self.assertIsInstance(payload["calibration"], list)

    def test_wiki_modes_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as caught:
            main(["wiki", str(self.repo), "--emit-feed", "--calibrate"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
