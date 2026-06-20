"""The OPEN-WORLD invariant for static code-fact families.

Pins the named open-world gaps (each GROUND-TRUTHED by running the real extractor, so a
claimed gap is demonstrable, never merely asserted — the B2 review lesson), and the
`codas impact` consumer that renders the lower-bound caveat. Replaces the withdrawn graded
"soundness level" (which carried no decision: static code facts are uniformly open-world).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from codas.adapters.callgraph import CallFact, CallFacts, extract_call_facts_from_parsed
from codas.adapters.python import extract_symbol_facts_from_parsed
from codas.adapters.python_parse import parse_sources
from codas.app.impact import compute_impact, render_impact_text, run_impact
from codas.facts.openworld import OPEN_WORLD_GAPS, open_world_gaps

REPO = Path(__file__).resolve().parents[1]


def _edge(caller_module, caller_symbol, callee_module, callee_symbol):
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


class OpenWorldGapsLookup(unittest.TestCase):
    def test_code_families_are_open(self):
        for family in ("symbols", "imports", "calls"):
            self.assertTrue(open_world_gaps(family), family)

    def test_unlisted_family_returns_empty_not_a_closed_world_claim(self):
        # A family not in the consumer-scoped gap list returns () — this is NOT an
        # assertion of closed-world (doc/wiki path refs are open-world yet unlisted; a
        # future generic verifier must consult the module doc, never read () as closed).
        self.assertEqual(open_world_gaps("units"), ())          # config family
        self.assertEqual(open_world_gaps("doc_claims"), ())     # open-world, no consumer yet
        self.assertEqual(open_world_gaps("nonsense"), ())       # unknown


class GapsAreGroundTruthed(unittest.TestCase):
    """Each disclosed gap must be DEMONSTRABLE by the real extractor, not asserted."""

    def test_calls_misses_out_of_body_call_forms(self):
        src = {
            "pkg/__init__.py": "",
            "pkg/m.py": (
                "def helper(): pass\n"
                "def deco(f): return f\n"
                "top = helper()\n"            # module-level -> DROPPED
                "@deco\n"                       # decorator -> DROPPED
                "def g(x=helper()):\n"          # default-arg -> DROPPED
                "    return helper()\n"         # in-body -> CAPTURED
                "class C:\n"
                "    y = helper()\n"            # class-body -> DROPPED
            ),
        }
        facts = extract_call_facts_from_parsed(parse_sources(src))
        callers = {(e.caller_symbol, e.caller_class) for e in facts.edges}
        self.assertEqual(callers, {("g", "")})  # only the in-body call survives
        self.assertTrue(
            any("outside a function/method body" in g for g in open_world_gaps("calls"))
        )

    def test_symbols_misses_conditional_and_dynamic_defs(self):
        src = {
            "pkg/__init__.py": "",
            "pkg/m.py": (
                "def normal(): pass\n"
                "if True:\n"
                "    def conditional(): pass\n"   # conditional top-level -> DROPPED
                "globals()['dynamic'] = normal\n"  # dynamic -> DROPPED
            ),
        }
        syms = extract_symbol_facts_from_parsed(parse_sources(src))
        names = {d.name for d in syms.definitions if d.module == "pkg/m.py"}
        self.assertEqual(names, {"normal"})
        gaps = " ".join(open_world_gaps("symbols"))
        self.assertIn("conditionally-defined", gaps)
        self.assertIn("dynamically-created", gaps)

    def test_imports_does_not_over_claim_conditional_local(self):
        # ast.walk DOES reach conditional/function-local import statements, so the gap
        # list must NOT claim they are missed (the B2 over-claim that was removed).
        src = {
            "pkg/__init__.py": "",
            "pkg/a.py": "x = 1\n",
            "pkg/b.py": "if True:\n    from pkg import a\ndef f():\n    from pkg import a as a2\n",
        }
        from codas.adapters.python import extract_import_facts_from_parsed

        edges = extract_import_facts_from_parsed(parse_sources(src)).imports
        # the conditional `from pkg import a` IS reached
        self.assertTrue(any(e.target in ("pkg", "pkg.a") for e in edges))
        gaps = " ".join(open_world_gaps("imports"))
        self.assertNotIn("function-local imports not reached", gaps)
        self.assertNotIn("conditional or function-local imports not reached", gaps)
        self.assertIn("dynamic imports", gaps)


class ImpactConsumer(unittest.TestCase):
    def test_result_carries_open_world_lower_bound(self):
        result = compute_impact(_facts(_edge("a", "caller", "b", "target")), "target", REPO)
        self.assertTrue(result["open_world"]["is_lower_bound"])
        self.assertEqual(result["open_world"]["misses"], list(open_world_gaps("calls")))

    def test_render_caveat_when_affected(self):
        facts = _facts(
            _edge("a", "caller", "b", "target"),
            _edge("c", "outer", "a", "caller"),
        )
        text = render_impact_text(compute_impact(facts, "target", REPO))
        self.assertIn("open-world", text)
        self.assertIn("lower bound", text)

    def test_render_caveat_on_miss(self):
        # A miss discloses the open-world caveat too (absence may be a missed call).
        text = render_impact_text(compute_impact(_facts(_edge("a", "c", "b", "t")), "ghost", REPO))
        self.assertIn("not found", text)
        self.assertIn("open-world", text)
        self.assertIn("not proof of none", text)

    def test_impact_json_byte_identical(self):
        facts = _facts(_edge("z", "z", "t", "t"), _edge("a", "a", "t", "t"))
        a = json.dumps(compute_impact(facts, "t", REPO), sort_keys=True)
        b = json.dumps(compute_impact(facts, "t", REPO), sort_keys=True)
        self.assertEqual(a, b)

    def test_run_impact_on_self_carries_open_world(self):
        result = run_impact(REPO, "compute_impact")
        self.assertTrue(result["open_world"]["is_lower_bound"])


class InventoryHasNoSoundnessBlock(unittest.TestCase):
    def test_fact_soundness_block_removed(self):
        from codas.app.inventory import run_inventory

        inventory = run_inventory(REPO)
        self.assertNotIn("fact_soundness", inventory)


if __name__ == "__main__":
    unittest.main()
