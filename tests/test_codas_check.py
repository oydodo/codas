from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codas.app.check import run_check
from codas.config.loader import load_codas_config


class CodasCheckTests(unittest.TestCase):
    def test_load_config_reads_sources_and_task_globs(self) -> None:
        repo = Path.cwd()
        config = load_codas_config(repo / ".codas" / "config.yml")

        self.assertIn("docs/codas-design.html", config.authoritative_sources)
        self.assertIn("docs/codas-implementation-plan.html", config.authoritative_sources)
        self.assertIn(".trellis/tasks/*/implement.jsonl", config.workflow_task_globs)
        self.assertIn(".trellis/tasks/*/check.jsonl", config.workflow_task_globs)
        self.assertEqual(config.dogfooding_protocol, "docs/codas-design.html#dogfooding-protocol")

    def test_codas_self_check_has_no_error_findings(self) -> None:
        repo = Path.cwd()
        report = run_check(repo)
        errors = [finding.to_json() for finding in report.findings if finding.severity == "error"]

        self.assertEqual(errors, [])

    def test_codas_self_check_has_no_stale_or_deprecated_findings(self) -> None:
        # The new P2 policies must stay quiet on this repo (dogfooding invariant).
        # Assert by check_id, not just severity: stale_claim is a warning, so a
        # warning-only regression must still fail here.
        repo = Path.cwd()
        report = run_check(repo)
        ids = [finding.check_id for finding in report.findings]

        self.assertNotIn("stale-claim", ids)
        self.assertNotIn("deprecated-path-used", ids)
        self.assertNotIn("missing-structure-owner", ids)
        self.assertNotIn("structure-drift", ids)
        self.assertNotIn("duplicate-symbol", ids)
        self.assertNotIn("duplicate-implementation", ids)
        self.assertNotIn("claim-schema-invalid", ids)
        self.assertNotIn("dependency-direction", ids)
        self.assertNotIn("stale-wiki-claim", ids)

    def test_scan_context_built_once_and_forwarded_to_policies(self) -> None:
        # P3 orchestration contract: run_check builds exactly one ScanContext and
        # threads that same object into every fact-consuming policy.
        repo = Path.cwd()
        with mock.patch("codas.app.check.build_scan_context") as build, mock.patch(
            "codas.app.check.check_stale_claim", return_value=[]
        ) as stale, mock.patch(
            "codas.app.check.check_stale_html_claim", return_value=[]
        ) as stale_html, mock.patch(
            "codas.app.check.check_duplicate_symbol", return_value=[]
        ) as dup_symbol, mock.patch(
            "codas.app.check.check_duplicate_implementation", return_value=[]
        ) as dup_impl, mock.patch(
            "codas.app.check.check_dependency_direction", return_value=[]
        ) as dep_dir, mock.patch(
            "codas.app.check.check_stale_wiki_claim", return_value=[]
        ) as stale_wiki, mock.patch(
            "codas.app.check.check_fact_coupling", return_value=[]
        ) as fact_coupling, mock.patch(
            "codas.app.check.check_generated_wiki_drift", return_value=[]
        ) as gen_drift, mock.patch(
            "codas.app.check.check_code_anchor", return_value=[]
        ) as code_anchor, mock.patch(
            "codas.app.check.check_policy_registry", return_value=[]
        ) as policy_registry:
            run_check(repo)

        self.assertEqual(build.call_count, 1)
        for spy in (stale, stale_html, dup_symbol, dup_impl, dep_dir, stale_wiki, fact_coupling, gen_drift, code_anchor, policy_registry):
            self.assertEqual(spy.call_count, 1)
            self.assertIs(spy.call_args.args[0], build.return_value)

    def test_missing_declared_authoritative_source_is_error(self) -> None:
        with codas_fixture() as repo:
            config = repo / ".codas" / "config.yml"
            config.write_text(
                """\
version: 1
constraint_sources:
  authoritative:
    - missing.md
workflow:
  adapter: trellis
  root: .trellis
  task_globs:
    - .trellis/tasks/*/task.json
    - .trellis/tasks/*/prd.md
    - .trellis/tasks/*/implement.jsonl
    - .trellis/tasks/*/check.jsonl
dogfooding:
  protocol: docs/codas-design.html#dogfooding-protocol
""",
            )

            report = run_check(repo)
            ids = {finding.check_id for finding in report.findings}

            self.assertIn("declared-source-missing", ids)

    def test_invalid_policies_yaml_is_error(self) -> None:
        with codas_fixture() as repo:
            write(repo / ".codas" / "config.yml", VALID_CONFIG)
            write(repo / ".codas" / "policies.yml", "version: 1\n  bad_indent: true\n")

            report = run_check(repo)
            ids = {finding.check_id for finding in report.findings}

            self.assertIn("policy-load-error", ids)

    def test_cli_json_report_runs(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "codas", "check", ".", "--json"],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("findings", payload)
        self.assertTrue(payload["ok"])


class codas_fixture:
    def __enter__(self) -> Path:
        self.tmp = tempfile.TemporaryDirectory()
        repo = Path(self.tmp.name)
        write(repo / ".codas" / "policies.yml", "version: 1\npolicies: {}\n")
        write(repo / ".codas" / "waivers.yml", "version: 1\nwaivers: []\n")
        write(repo / "docs" / "codas-design.html", '<h2 id="dogfooding-protocol">Dogfooding</h2>\n')
        task = repo / ".trellis" / "tasks" / "06-17-example"
        write(task / "task.json", "{}\n")
        write(task / "prd.md", "# PRD\n")
        write(task / "implement.jsonl", "{}\n")
        write(task / "check.jsonl", "{}\n")
        return repo

    def __exit__(self, exc_type, exc, tb) -> None:
        self.tmp.cleanup()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


VALID_CONFIG = """\
version: 1
constraint_sources:
  authoritative:
    - docs/codas-design.html
workflow:
  adapter: trellis
  root: .trellis
  task_globs:
    - .trellis/tasks/*/task.json
    - .trellis/tasks/*/prd.md
    - .trellis/tasks/*/implement.jsonl
    - .trellis/tasks/*/check.jsonl
dogfooding:
  protocol: docs/codas-design.html#dogfooding-protocol
"""


if __name__ == "__main__":
    unittest.main()
