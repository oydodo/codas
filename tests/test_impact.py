from __future__ import annotations

import json
import unittest
from pathlib import Path

from codas.adapters.callgraph import CallFact, CallFacts
from codas.app.impact import compute_impact, render_impact_text, run_impact

REPO = Path(__file__).resolve().parents[1]


def _edge(
    caller_module,
    caller_symbol,
    callee_module,
    callee_symbol,
    *,
    caller_class="",
    callee_class="",
    resolution="direct",
):
    """A CallFact with path == module (1:1) so node identity is easy to assert."""
    return CallFact(
        caller_module=caller_module,
        caller_class=caller_class,
        caller_symbol=caller_symbol,
        caller_path=f"{caller_module}.py",
        caller_line=1,
        callee_module=callee_module,
        callee_class=callee_class,
        callee_symbol=callee_symbol,
        callee_path=f"{callee_module}.py",
        callee_line=1,
        resolution=resolution,
    )


def _facts(*edges):
    return CallFacts(edges=tuple(edges), skipped=())


def _names(rows):
    return [(r["module"], r["class"], r["symbol"]) for r in rows]


class ResolveTargets(unittest.TestCase):
    def test_bare_symbol_matches(self):
        facts = _facts(_edge("a", "caller", "b", "target"))
        result = compute_impact(facts, "target", REPO)
        self.assertEqual(result["target_kind"], "symbol")
        self.assertEqual(_names(result["matched"]), [("b", "", "target")])

    def test_dotted_symbol_matches_module_qualified(self):
        facts = _facts(_edge("a", "caller", "pkg.b", "target"))
        result = compute_impact(facts, "pkg.b.target", REPO)
        self.assertEqual(_names(result["matched"]), [("pkg.b", "", "target")])

    def test_class_qualified_method(self):
        facts = _facts(_edge("a", "caller", "b", "m", callee_class="C"))
        by_method = compute_impact(facts, "C.m", REPO)
        self.assertEqual(_names(by_method["matched"]), [("b", "C", "m")])
        by_dotted = compute_impact(facts, "b.C.m", REPO)
        self.assertEqual(_names(by_dotted["matched"]), [("b", "C", "m")])

    def test_bare_name_unions_same_named_nodes(self):
        # A function `run` and a method `Svc.run` both match the bare spec `run`.
        facts = _facts(
            _edge("a", "ca", "b", "run"),
            _edge("a", "cb", "b", "run", callee_class="Svc"),
        )
        result = compute_impact(facts, "run", REPO)
        self.assertEqual(
            _names(result["matched"]), [("b", "", "run"), ("b", "Svc", "run")]
        )

    def test_unknown_symbol_is_empty_not_error(self):
        facts = _facts(_edge("a", "caller", "b", "target"))
        result = compute_impact(facts, "ghost", REPO)
        self.assertEqual(result["matched"], [])
        self.assertEqual(result["affected"], [])
        self.assertIn("not found", render_impact_text(result))

    def test_caller_only_symbol_resolves_with_zero_callers(self):
        # `caller` is never itself called -> found target, no impact (distinct from a miss).
        facts = _facts(_edge("a", "caller", "b", "target"))
        result = compute_impact(facts, "caller", REPO)
        self.assertEqual(_names(result["matched"]), [("a", "", "caller")])
        self.assertEqual(result["affected"], [])
        self.assertIn("affects nothing", render_impact_text(result))


class PathTargets(unittest.TestCase):
    def test_path_target_collects_file_symbols(self):
        # lib.py defines g; caller_mod.f calls lib.g; other.h calls caller_mod.f.
        # Impact of lib.py = transitive callers of g = {caller_mod.f (1), other.h (2)}.
        facts = _facts(
            _edge("caller_mod", "f", "lib", "g"),
            _edge("other", "h", "caller_mod", "f"),
        )
        result = compute_impact(facts, "lib.py", REPO)
        self.assertEqual(result["target_kind"], "path")
        self.assertEqual(result["target"], "lib.py")
        self.assertEqual(_names(result["matched"]), [("lib", "", "g")])
        self.assertEqual(
            _names(result["affected"]),
            [("caller_mod", "", "f"), ("other", "", "h")],
        )

    def test_path_detection_by_slash(self):
        facts = _facts(_edge("a", "c", "pkg/mod", "t"))
        result = compute_impact(facts, "pkg/mod.py", REPO)
        self.assertEqual(result["target_kind"], "path")

    def test_leading_dot_slash_normalized(self):
        facts = _facts(_edge("a", "c", "lib", "g"))
        result = compute_impact(facts, "./lib.py", REPO)
        self.assertEqual(result["target"], "lib.py")
        self.assertEqual(_names(result["matched"]), [("lib", "", "g")])

    def test_windows_backslash_path_normalized(self):
        facts = _facts(_edge("a", "c", "pkg/mod", "t"))
        result = compute_impact(facts, "pkg\\mod.py", REPO)
        self.assertEqual(result["target_kind"], "path")
        self.assertEqual(result["target"], "pkg/mod.py")
        self.assertEqual(_names(result["matched"]), [("pkg/mod", "", "t")])

    def test_absolute_path_under_repo_resolves_relative(self):
        # An agent may pass an absolute path; it resolves against the repo root.
        facts = _facts(_edge("caller", "c", "src/codas/app/impact", "g"))
        # callee_path is "src/codas/app/impact.py"; pass it absolute.
        abs_target = str(REPO / "src" / "codas" / "app" / "impact.py")
        result = compute_impact(facts, abs_target, REPO)
        self.assertEqual(result["target_kind"], "path")
        self.assertEqual(result["target"], "src/codas/app/impact.py")
        self.assertEqual(_names(result["matched"]), [("src/codas/app/impact", "", "g")])


class ReverseReachability(unittest.TestCase):
    def test_transitive_distance(self):
        # d -> c -> b -> target ; distances 3,2,1
        facts = _facts(
            _edge("c", "c", "target_mod", "target"),
            _edge("b", "b", "c", "c"),
            _edge("d", "d", "b", "b"),
        )
        result = compute_impact(facts, "target", REPO)
        dist = {(r["symbol"]): r["distance"] for r in result["affected"]}
        self.assertEqual(dist, {"c": 1, "b": 2, "d": 3})
        self.assertEqual(
            result["affected_paths"], ["b.py", "c.py", "d.py"]
        )

    def test_cycle_terminates(self):
        # a -> b -> a (mutual). Trace callers of a: b (1), then a again at 2 but a is the
        # target (distance 0) so it is not re-added; terminates.
        facts = _facts(
            _edge("a", "a", "b", "b"),
            _edge("b", "b", "a", "a"),
        )
        result = compute_impact(facts, "a", REPO)
        self.assertEqual(_names(result["affected"]), [("b", "", "b")])
        self.assertEqual(result["affected"][0]["distance"], 1)

    def test_self_recursion_excluded(self):
        facts = _facts(_edge("a", "a", "a", "a"))  # a calls itself
        result = compute_impact(facts, "a", REPO)
        self.assertEqual(result["affected"], [])  # target excluded from its own callers

    def test_diamond_uses_min_distance(self):
        # target <- b <- top ; target <- c <- top  (top reaches target two ways)
        facts = _facts(
            _edge("b", "b", "t", "t"),
            _edge("c", "c", "t", "t"),
            _edge("top", "top", "b", "b"),
            _edge("top", "top", "c", "c"),
        )
        result = compute_impact(facts, "t", REPO)
        dist = {r["symbol"]: r["distance"] for r in result["affected"]}
        self.assertEqual(dist, {"b": 1, "c": 1, "top": 2})


class Determinism(unittest.TestCase):
    def test_compute_impact_byte_identical(self):
        facts = _facts(
            _edge("z", "z", "t", "t"),
            _edge("a", "a", "t", "t"),
            _edge("m", "m", "a", "a"),
        )
        a = json.dumps(compute_impact(facts, "t", REPO), sort_keys=True)
        b = json.dumps(compute_impact(facts, "t", REPO), sort_keys=True)
        self.assertEqual(a, b)

    def test_run_impact_on_self_is_deterministic(self):
        a = json.dumps(run_impact(REPO, "compute_impact"), sort_keys=True)
        b = json.dumps(run_impact(REPO, "compute_impact"), sort_keys=True)
        self.assertEqual(a, b)
        # compute_impact is called by run_impact -> at least one first-party caller.
        result = run_impact(REPO, "compute_impact")
        callers = {r["symbol"] for r in result["affected"]}
        self.assertIn("run_impact", callers)


if __name__ == "__main__":
    unittest.main()
