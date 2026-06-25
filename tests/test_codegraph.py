from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codas.adapters.callgraph import CallFact, CallFacts
from codas.adapters.codegraph import (
    CodeGraphCallFact,
    CodeGraphCallFacts,
    extract_codegraph_calls,
    parse_codegraph_calls,
)
from codas.app.impact import render_impact_text, run_impact
from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.preflight import build_context_pack
from codas.app.check import run_check
from codas.config.loader import load_codas_config
from codas.facts.context import ScanContext, build_scan_context
from tests._repo import build_golden
from tests.test_preflight import _repo as write_preflight_repo

REPO = Path(__file__).resolve().parents[1]


def _call(caller: str, callee: str) -> CallFact:
    return CallFact(
        caller_module=caller,
        caller_class="",
        caller_symbol="caller",
        caller_path=f"{caller}.py",
        caller_line=1,
        callee_module=callee,
        callee_class="",
        callee_symbol="target",
        callee_path=f"{callee}.py",
        callee_line=2,
        resolution="direct",
    )


def _codegraph(caller: str, callee: str, resolution: str = "heuristic") -> CodeGraphCallFact:
    return CodeGraphCallFact(
        caller_module=caller,
        caller_class="",
        caller_symbol="caller",
        caller_path=f"{caller}.py",
        caller_line=3,
        callee_module=callee,
        callee_class="",
        callee_symbol="target",
        callee_path=f"{callee}.py",
        callee_line=2,
        resolution=resolution,
    )


class CodeGraphAdapterTests(unittest.TestCase):
    def test_absent_binary_is_empty(self) -> None:
        facts = extract_codegraph_calls(REPO, (), executable="/no/such/codegraph")

        self.assertEqual(facts.edges, ())
        self.assertEqual(facts.skipped, ("codegraph: executable not found",))

    def test_fake_output_is_parsed_and_sorted(self) -> None:
        payload = json.dumps(
            {
                "edges": [
                    {
                        "caller": {"path": "z.js", "symbol": "z", "line": "7"},
                        "callee": {"path": "pkg/t.py", "symbol": "target", "line": 1},
                        "resolution": "name",
                    },
                    {
                        "caller_path": "bad.js",
                        "callee_path": "pkg/t.py",
                        "callee_symbol": "target",
                    },
                    {
                        "callerPath": "./a.js",
                        "callerSymbol": "a",
                        "calleePath": "pkg/t.py",
                        "calleeSymbol": "target",
                    },
                ]
            }
        )

        facts = parse_codegraph_calls(payload, REPO, ("a.js", "z.js", "pkg/t.py"))

        self.assertEqual([edge.caller_path for edge in facts.edges], ["a.js", "z.js"])
        self.assertEqual(facts.edges[0].resolution, "heuristic")
        self.assertEqual(facts.edges[1].resolution, "name")
        self.assertEqual(facts.edges[0].provenance, "codegraph")
        self.assertEqual(facts.skipped, ("edge[1]: caller missing-symbol",))


class CodeGraphImpactTests(unittest.TestCase):
    def test_run_impact_merges_mixed_sources_for_same_node(self) -> None:
        class FakeContext:
            def calls(self) -> CallFacts:
                return CallFacts(edges=(_call("app", "lib"),), skipped=())

            def codegraph_calls(self) -> CodeGraphCallFacts:
                return CodeGraphCallFacts(edges=(_codegraph("app", "lib"),), skipped=())

        with mock.patch("codas.app.impact.build_scan_context", return_value=FakeContext()):
            result = run_impact(REPO, "target")

        self.assertEqual(len(result["affected"]), 1)
        row = result["affected"][0]
        self.assertEqual(row["module"], "app")
        self.assertEqual(row["provenance"], ["codas", "codegraph"])
        self.assertEqual(len(row["via"]), 2)
        self.assertIn("provenance=codas,codegraph", render_impact_text(result))


class CodeGraphPreflightTests(unittest.TestCase):
    def test_absent_codegraph_keeps_preflight_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            write_preflight_repo(repo, with_task=True)
            env = {"CODAS_CODEGRAPH": "/no/such/codegraph"}
            with mock.patch.dict(os.environ, env, clear=False):
                first = json.dumps(build_context_pack(repo, task_id="demo"), sort_keys=True)
                second = json.dumps(build_context_pack(repo, task_id="demo"), sort_keys=True)

        self.assertEqual(first, second)
        self.assertNotIn("advisory_reuse_hints", json.loads(first))

    def test_fake_codegraph_adds_advisory_reuse_hints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            write_preflight_repo(repo, with_task=True)
            fake = repo / "fake-codegraph"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'edges': [{"
                "'callerPath': 'web/app.js', 'callerSymbol': 'render', "
                "'calleePath': 'src/service.py', 'calleeSymbol': 'load', "
                "'resolution': 'heuristic'}]}))\n"
            )
            fake.chmod(0o755)

            with mock.patch.dict(os.environ, {"CODAS_CODEGRAPH": str(fake)}, clear=False):
                pack = build_context_pack(repo, task_id="demo")

        hints = pack["advisory_reuse_hints"]
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["provenance"], "codegraph")
        self.assertEqual(hints[0]["callee_symbol"], "load")


class CodeGraphIsolationTests(unittest.TestCase):
    def test_inventory_is_byte_identical_after_codegraph_accessor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = build_golden(Path(directory), commit=True).root
            config = load_codas_config(repo / ".codas" / "config.yml")
            ctx = build_scan_context(repo, config)

            with mock.patch.dict(os.environ, {"CODAS_CODEGRAPH": "/no/such/codegraph"}, clear=False):
                before = render_inventory_json(run_inventory(repo, ctx=ctx))
                ctx.codegraph_calls()
                after = render_inventory_json(run_inventory(repo, ctx=ctx))

        self.assertEqual(before, after)

    def test_snapshot_and_fact_delta_ignore_codegraph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = build_golden(Path(directory), commit=True).root
            config = load_codas_config(repo / ".codas" / "config.yml")
            ctx = build_scan_context(repo, config)

            with mock.patch.dict(os.environ, {"CODAS_CODEGRAPH": "/no/such/codegraph"}, clear=False):
                snapshot = ctx.working_snapshot()
                delta = ctx.fact_delta()
                ctx.codegraph_calls()

        self.assertEqual(ctx.working_snapshot(), snapshot)
        self.assertEqual(ctx.fact_delta(), delta)

    def test_run_check_never_calls_codegraph_accessor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = build_golden(Path(directory), commit=True).root
            with mock.patch.object(
                ScanContext,
                "codegraph_calls",
                side_effect=AssertionError("codegraph must not gate"),
            ):
                report = run_check(repo)

        self.assertEqual(report.findings, [])


if __name__ == "__main__":
    unittest.main()
