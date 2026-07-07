from __future__ import annotations

import json
import os
import sqlite3
import subprocess
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
from codas.app.query import run_query, run_schema
from codas.config.loader import load_codas_config
from codas.core.provenance import inventory_hash
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


def _codegraph(
    caller: str,
    callee: str,
    resolution: str = "heuristic",
    *,
    caller_path: str | None = None,
    callee_path: str | None = None,
) -> CodeGraphCallFact:
    return CodeGraphCallFact(
        caller_module=caller,
        caller_class="",
        caller_symbol="caller",
        caller_path=caller_path or f"{caller}.py",
        caller_line=3,
        callee_module=callee,
        callee_class="",
        callee_symbol="target",
        callee_path=callee_path or f"{callee}.py",
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

    def test_real_codegraph_cli_reads_local_sqlite_index_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            index = repo / ".codegraph"
            index.mkdir()
            db = index / "codegraph.db"
            with sqlite3.connect(db) as conn:
                conn.executescript(
                    """
                    CREATE TABLE nodes (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL,
                        qualified_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        language TEXT NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        start_column INTEGER NOT NULL,
                        end_column INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    );
                    CREATE TABLE edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        metadata TEXT,
                        line INTEGER,
                        col INTEGER,
                        provenance TEXT
                    );
                    """
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("caller", "function", "render", "render", "web/app.js", "javascript", 4, 6, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("callee", "function", "load", "load", "src/service.py", "python", 8, 10, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO edges (source, target, kind, line, provenance) VALUES (?, ?, ?, ?, ?)",
                    ("caller", "callee", "calls", 5, "heuristic"),
                )

            with mock.patch(
                "subprocess.run", side_effect=AssertionError("status should not run")
            ):
                facts = extract_codegraph_calls(repo, ("web/app.js", "src/service.py"))

        self.assertEqual(len(facts.edges), 1)
        edge = facts.edges[0]
        self.assertEqual(edge.caller_module, "web.app")
        self.assertEqual(edge.caller_symbol, "render")
        self.assertEqual(edge.callee_module, "src.service")
        self.assertEqual(edge.callee_symbol, "load")
        self.assertEqual(edge.resolution, "calls:heuristic")

    def test_status_index_path_fallback_when_local_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            index = Path(directory) / "external-index"
            index.mkdir()
            db = index / "codegraph.db"
            with sqlite3.connect(db) as conn:
                conn.executescript(
                    """
                    CREATE TABLE nodes (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL,
                        qualified_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        language TEXT NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        start_column INTEGER NOT NULL,
                        end_column INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    );
                    CREATE TABLE edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        metadata TEXT,
                        line INTEGER,
                        col INTEGER,
                        provenance TEXT
                    );
                    """
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("caller", "function", "render", "render", "web/app.js", "javascript", 4, 6, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("callee", "function", "load", "load", "src/service.py", "python", 8, 10, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO edges (source, target, kind, line) VALUES (?, ?, ?, ?)",
                    ("caller", "callee", "instantiates", 5),
                )

            status = json.dumps({"initialized": True, "indexPath": index.as_posix()})
            completed = subprocess.CompletedProcess(
                args=["codegraph", "status"],
                returncode=0,
                stdout=status,
                stderr="",
            )
            with mock.patch("subprocess.run", return_value=completed) as run:
                facts = extract_codegraph_calls(repo, ("web/app.js", "src/service.py"))

        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["codegraph", "status", "--json"])
        self.assertEqual(len(facts.edges), 1)
        self.assertEqual(facts.edges[0].resolution, "instantiates")

    def test_status_path_argument_is_second_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            index = Path(directory) / "external-index"
            index.mkdir()
            db = index / "codegraph.db"
            with sqlite3.connect(db) as conn:
                conn.executescript(
                    """
                    CREATE TABLE nodes (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL,
                        qualified_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        language TEXT NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        start_column INTEGER NOT NULL,
                        end_column INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    );
                    CREATE TABLE edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        metadata TEXT,
                        line INTEGER,
                        col INTEGER,
                        provenance TEXT
                    );
                    """
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("caller", "function", "render", "render", "web/app.js", "javascript", 4, 6, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("callee", "function", "load", "load", "src/service.py", "python", 8, 10, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO edges (source, target, kind, line) VALUES (?, ?, ?, ?)",
                    ("caller", "callee", "calls", 5),
                )

            status = json.dumps({"initialized": True, "indexPath": index.as_posix()})
            failed = subprocess.CompletedProcess(
                args=["codegraph", "status"],
                returncode=1,
                stdout="",
                stderr="unable to open database file",
            )
            completed = subprocess.CompletedProcess(
                args=["codegraph", "status", repo.as_posix()],
                returncode=0,
                stdout=status,
                stderr="",
            )
            with mock.patch("subprocess.run", side_effect=[failed, completed]) as run:
                facts = extract_codegraph_calls(repo, ("web/app.js", "src/service.py"))

        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["codegraph", "status", "--json", repo.as_posix()],
        )
        self.assertEqual(len(facts.edges), 1)

    def test_db_paths_are_normalized_against_repo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            index = repo / ".codegraph"
            index.mkdir()
            db = index / "codegraph.db"
            with sqlite3.connect(db) as conn:
                conn.executescript(
                    """
                    CREATE TABLE nodes (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL,
                        qualified_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        language TEXT NOT NULL,
                        start_line INTEGER NOT NULL,
                        end_line INTEGER NOT NULL,
                        start_column INTEGER NOT NULL,
                        end_column INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    );
                    CREATE TABLE edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        target TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        metadata TEXT,
                        line INTEGER,
                        col INTEGER,
                        provenance TEXT
                    );
                    """
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("caller", "method", "render", "View::render", str(repo / "web/app.js"), "javascript", 4, 6, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("callee", "function", "load", "load", "./src/service.py", "python", 8, 10, 0, 0, 1),
                )
                conn.execute(
                    "INSERT INTO edges (source, target, kind, line) VALUES (?, ?, ?, ?)",
                    ("caller", "callee", "calls", 5),
                )

            facts = extract_codegraph_calls(repo, ("web/app.js", "src/service.py"))

        self.assertEqual(len(facts.edges), 1)
        self.assertEqual(facts.edges[0].caller_path, "web/app.js")
        self.assertEqual(facts.edges[0].caller_class, "View")
        self.assertEqual(facts.edges[0].callee_path, "src/service.py")


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

    def test_run_impact_includes_non_python_advisory_edge(self) -> None:
        class FakeContext:
            def calls(self) -> CallFacts:
                return CallFacts(edges=(), skipped=())

            def codegraph_calls(self) -> CodeGraphCallFacts:
                return CodeGraphCallFacts(
                    edges=(
                        _codegraph(
                            "web.app",
                            "src.service",
                            "calls",
                            caller_path="web/app.js",
                            callee_path="src/service.py",
                        ),
                    ),
                    skipped=(),
                )

        with mock.patch("codas.app.impact.build_scan_context", return_value=FakeContext()):
            result = run_impact(REPO, "target")

        self.assertEqual(result["affected"][0]["path"], "web/app.js")
        self.assertEqual(result["affected"][0]["provenance"], ["codegraph"])
        self.assertEqual(result["affected"][0]["via"][0]["source"], "codegraph")
        self.assertIn("web/app.js  provenance=codegraph", render_impact_text(result))


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
                before_hash = inventory_hash(before)
                ctx.codegraph_calls()
                after = render_inventory_json(run_inventory(repo, ctx=ctx))
                after_hash = inventory_hash(after)

        self.assertEqual(before, after)
        self.assertEqual(before_hash, after_hash)

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

    def test_query_calls_and_schema_exclude_codegraph(self) -> None:
        with mock.patch.object(
            ScanContext,
            "codegraph_calls",
            side_effect=AssertionError("codegraph must not feed query"),
        ):
            rows = run_query(REPO, "calls", [])
            schema = run_schema(REPO)

        self.assertTrue(rows)
        self.assertIn("caller_symbol", schema["calls"]["fields"])
        self.assertNotIn("provenance", schema["calls"]["fields"])


if __name__ == "__main__":
    unittest.main()
