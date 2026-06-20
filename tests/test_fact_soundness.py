"""B2 — fact soundness qualifier.

Pins the soundness manifest + the ``meet`` family algebra, the new inventory
``fact_soundness`` block (and that it stays byte-identical 2x), and the ``calls``
soundness the ``codas impact`` consumer now carries (so the impact set reads as a
lower bound). Mirrors test_impact / test_fact_delta_substrate style.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from codas.adapters.callgraph import CallFact, CallFacts
from codas.app.impact import compute_impact, render_impact_text, run_impact
from codas.facts.soundness import (
    FACT_SOUNDNESS,
    FactFamilySoundness,
    SoundnessLevel,
    family_soundness,
    level_name,
    meet,
    meet_all,
)
from codas.structure.inventory import build_inventory

REPO = Path(__file__).resolve().parents[1]


def _edge(caller_module, caller_symbol, callee_module, callee_symbol):
    """A CallFact with path == module (1:1), matching test_impact's helper shape."""
    return CallFact(
        caller_module=caller_module,
        caller_class="",
        caller_symbol=caller_symbol,
        caller_path=f"{caller_module}.py",
        caller_line=1,
        callee_module=callee_module,
        callee_class="",
        callee_symbol=callee_symbol,
        callee_path=f"{callee_module}.py",
        callee_line=1,
        resolution="direct",
    )


def _facts(*edges):
    return CallFacts(edges=tuple(edges), skipped=())


class MeetAlgebra(unittest.TestCase):
    def test_levels_total_order(self):
        self.assertGreater(SoundnessLevel.EXACT, SoundnessLevel.SCOPED)
        self.assertGreater(SoundnessLevel.SCOPED, SoundnessLevel.APPROXIMATE_INCOMPLETE)
        self.assertEqual(int(SoundnessLevel.EXACT), 2)
        self.assertEqual(int(SoundnessLevel.SCOPED), 1)
        self.assertEqual(int(SoundnessLevel.APPROXIMATE_INCOMPLETE), 0)

    def test_meet_is_min_weakest_wins(self):
        exact = int(SoundnessLevel.EXACT)
        scoped = int(SoundnessLevel.SCOPED)
        approx = int(SoundnessLevel.APPROXIMATE_INCOMPLETE)
        self.assertEqual(meet(exact, exact), exact)
        self.assertEqual(meet(exact, scoped), scoped)
        self.assertEqual(meet(scoped, approx), approx)
        self.assertEqual(meet(approx, exact), approx)

    def test_meet_all_empty_is_exact(self):
        self.assertEqual(meet_all([]), int(SoundnessLevel.EXACT))

    def test_meet_all_folds_to_weakest(self):
        self.assertEqual(
            meet_all([int(SoundnessLevel.EXACT), int(SoundnessLevel.SCOPED)]),
            int(SoundnessLevel.SCOPED),
        )
        self.assertEqual(
            meet_all(
                [
                    int(SoundnessLevel.EXACT),
                    int(SoundnessLevel.SCOPED),
                    int(SoundnessLevel.APPROXIMATE_INCOMPLETE),
                ]
            ),
            int(SoundnessLevel.APPROXIMATE_INCOMPLETE),
        )

    def test_level_name_is_lowercase(self):
        self.assertEqual(level_name(SoundnessLevel.APPROXIMATE_INCOMPLETE), "approximate_incomplete")
        self.assertEqual(level_name(SoundnessLevel.SCOPED), "scoped")
        self.assertEqual(level_name(SoundnessLevel.EXACT), "exact")


class Manifest(unittest.TestCase):
    def test_three_families_present(self):
        self.assertEqual(sorted(FACT_SOUNDNESS), ["calls", "imports", "symbols"])

    def test_levels_as_specified(self):
        self.assertEqual(FACT_SOUNDNESS["symbols"].level, int(SoundnessLevel.SCOPED))
        self.assertEqual(
            FACT_SOUNDNESS["imports"].level, int(SoundnessLevel.APPROXIMATE_INCOMPLETE)
        )
        self.assertEqual(
            FACT_SOUNDNESS["calls"].level, int(SoundnessLevel.APPROXIMATE_INCOMPLETE)
        )

    def test_family_soundness_lookup(self):
        self.assertIsInstance(family_soundness("calls"), FactFamilySoundness)
        self.assertIsNone(family_soundness("doc_claims"))

    def test_as_dict_shape_and_lowercase_name(self):
        as_dict = FACT_SOUNDNESS["calls"].as_dict()
        self.assertEqual(sorted(as_dict), ["family", "level", "scope", "under_approximates"])
        self.assertEqual(as_dict["family"], "calls")
        self.assertEqual(as_dict["level"], "approximate_incomplete")  # name, not int
        self.assertIsInstance(as_dict["scope"], str)
        self.assertEqual(as_dict["under_approximates"], sorted(as_dict["under_approximates"]))

    def test_calls_manifest_discloses_the_body_only_scope_gap(self):
        gaps = FACT_SOUNDNESS["calls"].as_dict()["under_approximates"]
        # The scope gap codex B2 surfaced: only function/method BODIES are walked.
        self.assertTrue(
            any("outside a function/method body" in g for g in gaps),
            gaps,
        )

    def test_calls_gap_is_GROUND_TRUTHED_against_the_extractor(self):
        # codex B2 SHOULD-FIX: don't just assert the manifest matches a hardcoded list —
        # run the real call-graph extractor and PROVE the disclosed gaps are real, i.e.
        # calls outside a function/method body are actually dropped (so the manifest's
        # "outside a function/method body" disclosure is honest, not decorative).
        from codas.adapters.callgraph import extract_call_facts_from_parsed
        from codas.adapters.python_parse import parse_sources

        src = {
            "pkg/__init__.py": "",
            "pkg/m.py": (
                "def helper(): pass\n"
                "def deco(f): return f\n"
                "top = helper()\n"            # module-level call -> DROPPED
                "@deco\n"                       # decorator call -> DROPPED
                "def g(x=helper()):\n"          # default-arg call -> DROPPED
                "    return helper()\n"         # in-body call -> CAPTURED
                "class C:\n"
                "    y = helper()\n"            # class-body call -> DROPPED
            ),
        }
        facts = extract_call_facts_from_parsed(parse_sources(src))
        callers = {(e.caller_symbol, e.caller_class) for e in facts.edges}
        # Exactly the one in-body call is captured; the four out-of-body forms are absent.
        self.assertEqual(callers, {("g", "")})
        self.assertEqual(len(facts.edges), 1)

    def test_imports_manifest_does_not_over_claim_conditional_local(self):
        # codex B2 SHOULD-FIX: ast.walk DOES reach conditional/function-local imports,
        # so the manifest must NOT claim they are missed (it would over-state weakness).
        gaps = " ".join(FACT_SOUNDNESS["imports"].as_dict()["under_approximates"])
        self.assertNotIn("function-local imports not reached", gaps)
        self.assertNotIn("conditional or function-local imports not reached", gaps)
        self.assertIn("dynamic imports", gaps)


class InventoryBlock(unittest.TestCase):
    def test_inventory_has_fact_soundness_block(self):
        inventory = build_inventory(REPO)
        self.assertIn("fact_soundness", inventory)
        self.assertEqual(
            sorted(inventory["fact_soundness"]), ["calls", "imports", "symbols"]
        )
        for family, block in inventory["fact_soundness"].items():
            self.assertEqual(block["family"], family)
            self.assertIn(
                block["level"], {"exact", "scoped", "approximate_incomplete"}
            )

    def test_existing_fact_blocks_unchanged_shape(self):
        # fact_soundness is a NEW sibling: the existing fact blocks keep their shape
        # (no per-row soundness field leaked into calls/symbols/imports rows).
        inventory = build_inventory(REPO)
        if inventory["calls"]["edges"]:
            self.assertNotIn("soundness", inventory["calls"]["edges"][0])
        if inventory["symbols"]["definitions"]:
            self.assertNotIn("soundness", inventory["symbols"]["definitions"][0])

    def test_inventory_byte_identical_across_runs(self):
        a = json.dumps(build_inventory(REPO), sort_keys=True)
        b = json.dumps(build_inventory(REPO), sort_keys=True)
        self.assertEqual(a, b)


class ImpactConsumer(unittest.TestCase):
    def test_result_carries_calls_soundness(self):
        facts = _facts(_edge("a", "caller", "b", "target"))
        result = compute_impact(facts, "target", REPO)
        self.assertEqual(result["soundness"], family_soundness("calls").as_dict())
        self.assertEqual(result["soundness"]["level"], "approximate_incomplete")

    def test_render_shows_caveat_when_affected(self):
        facts = _facts(
            _edge("a", "caller", "b", "target"),
            _edge("c", "outer", "a", "caller"),
        )
        text = render_impact_text(compute_impact(facts, "target", REPO))
        self.assertIn("approximate_incomplete", text)
        self.assertIn("lower bound", text)

    def test_render_shows_caveat_when_matched_zero_callers(self):
        # `caller` is matched but has no callers: still a real target, caveat shown.
        facts = _facts(_edge("a", "caller", "b", "target"))
        text = render_impact_text(compute_impact(facts, "caller", REPO))
        self.assertIn("lower bound", text)
        self.assertIn("affects nothing", text)

    def test_render_miss_case_shows_a_soundness_note(self):
        # codex B2 SHOULD-FIX: a miss is exactly where approximation matters — the target
        # may be absent because the extractor missed the call. The miss path now discloses.
        facts = _facts(_edge("a", "caller", "b", "target"))
        text = render_impact_text(compute_impact(facts, "ghost", REPO))
        self.assertIn("not found", text)
        self.assertIn("approximate_incomplete", text)
        self.assertIn("not proof of none", text)
        # the miss note differs from the matched note (no "lower bound" framing)
        self.assertNotIn("lower bound", text)

    def test_impact_json_byte_identical(self):
        facts = _facts(
            _edge("z", "z", "t", "t"),
            _edge("a", "a", "t", "t"),
            _edge("m", "m", "a", "a"),
        )
        a = json.dumps(compute_impact(facts, "t", REPO), sort_keys=True)
        b = json.dumps(compute_impact(facts, "t", REPO), sort_keys=True)
        self.assertEqual(a, b)

    def test_run_impact_on_self_carries_soundness(self):
        result = run_impact(REPO, "compute_impact")
        self.assertEqual(result["soundness"]["level"], "approximate_incomplete")


class MeetReturnsPlainInt(unittest.TestCase):
    def test_meet_returns_plain_int_not_intenum(self):
        # codex B2 NIT: meet must not leak an IntEnum member to consumers.
        result = meet(SoundnessLevel.EXACT, SoundnessLevel.APPROXIMATE_INCOMPLETE)
        self.assertEqual(result, int(SoundnessLevel.APPROXIMATE_INCOMPLETE))
        self.assertNotIsInstance(result, SoundnessLevel)
        self.assertIs(type(result), int)
        self.assertIs(type(meet_all([SoundnessLevel.SCOPED])), int)


if __name__ == "__main__":
    unittest.main()
