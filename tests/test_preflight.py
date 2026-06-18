from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codas.app.preflight import build_context_pack
from codas.app.provenance import compute_provenance


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _repo(repo: Path, with_task: bool = False) -> None:
    _write(
        repo / ".codas" / "config.yml",
        "version: 1\nconstraint_sources:\n  authoritative:\n    - docs/b.html\n"
        "    - docs/a.html\n  supporting:\n    - AGENTS.md\n"
        "workflow:\n  adapter: trellis\n  root: .trellis\n  task_globs:\n"
        "    - .trellis/tasks/*/task.json\n"
        "dogfooding:\n  protocol: docs/a.html#d\n",
    )
    _write(
        repo / ".codas" / "structure.yml",
        "version: 1\nkind: structure_map\nunits:\n"
        "  root:\n    path: .\n    kind: package\n    owner: X\n    purpose: p\n"
        "    canonical_placement: c\n",
    )
    _write(
        repo / ".codas" / "policies.yml",
        "version: 1\npolicies:\n  stale_claim:\n    severity: warning\n"
        "  structure_drift:\n    severity: error\n",
    )
    _write(repo / "docs" / "a.html", '<h2 id="d">d</h2>\n')
    _write(repo / "docs" / "b.html", "<p>b</p>\n")
    if with_task:
        _write(
            repo / ".trellis" / "tasks" / "06-19-demo" / "task.json",
            json.dumps({"id": "demo", "status": "in_progress", "priority": "P2"}),
        )


class BuildContextPackTests(unittest.TestCase):
    def test_pack_shape_and_provenance_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _repo(repo)

            pack = build_context_pack(repo)

            self.assertEqual(pack["kind"], "context_pack")
            self.assertEqual(pack["read_first"], ["docs/a.html", "docs/b.html"])  # sorted
            self.assertEqual(pack["supporting"], ["AGENTS.md"])
            self.assertEqual(pack["dogfooding_protocol"], "docs/a.html#d")
            self.assertEqual(
                pack["policies"],
                [
                    {"id": "stale_claim", "severity": "warning"},
                    {"id": "structure_drift", "severity": "error"},
                ],
            )
            self.assertEqual(pack["provenance"], compute_provenance(repo))

    def test_deterministic_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _repo(repo)
            self.assertEqual(build_context_pack(repo), build_context_pack(repo))

    def test_task_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _repo(repo, with_task=True)

            matched = build_context_pack(repo, task_id="demo")
            self.assertIsNotNone(matched["task"])
            self.assertEqual(matched["task"]["id"], "demo")
            self.assertEqual(matched["task"]["status"], "in_progress")
            self.assertEqual(matched["available_tasks"], ["demo"])

            # unknown id -> task None; no id -> task None but tasks listed
            self.assertIsNone(build_context_pack(repo, task_id="nope")["task"])
            self.assertIsNone(build_context_pack(repo)["task"])
            self.assertEqual(build_context_pack(repo)["available_tasks"], ["demo"])


class PreflightCliTests(unittest.TestCase):
    def _run(self, repo: Path, *args: str):
        env = {**__import__("os").environ, "PYTHONPATH": str(Path.cwd() / "src")}
        return subprocess.run(
            [sys.executable, "-m", "codas", "preflight", ".", *args],
            cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, env=env,
        )

    def test_preflight_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _repo(repo, with_task=True)

            result = self._run(repo, "--json", "--task", "demo")

            self.assertEqual(result.returncode, 0, result.stderr)
            pack = json.loads(result.stdout)
            self.assertEqual(pack["kind"], "context_pack")
            self.assertEqual(pack["task"]["id"], "demo")

    def test_preflight_human_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _repo(repo)

            result = self._run(repo)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Read first:", result.stdout)

    def test_malformed_config_is_clean_error_not_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "config.yml", "version: 1\n  bad: indent\n")

            result = self._run(repo)

            self.assertEqual(result.returncode, 2)
            self.assertTrue(result.stdout == "" or "{" not in result.stdout)
            self.assertIn("preflight:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
