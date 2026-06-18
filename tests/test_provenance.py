from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.provenance import compute_provenance
from codas.core.provenance import digest, inventory_hash, policy_version


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _minimal_repo(repo: Path, policies: str) -> None:
    _write(
        repo / ".codas" / "config.yml",
        "version: 1\nconstraint_sources:\n  authoritative:\n    - docs/x.html\n"
        "workflow:\n  adapter: trellis\n  root: .trellis\n  task_globs:\n"
        "    - .trellis/tasks/*/task.json\n"
        "dogfooding:\n  protocol: docs/x.html#d\n",
    )
    _write(
        repo / ".codas" / "structure.yml",
        "version: 1\nkind: structure_map\nunits:\n"
        "  root:\n    path: .\n    kind: package\n    owner: X\n    purpose: p\n"
        "    canonical_placement: c\n",
    )
    _write(repo / ".codas" / "policies.yml", policies)
    _write(repo / "docs" / "x.html", '<h2 id="d">d</h2>\n')
    _write(repo / "src" / "a.py", "def alpha():\n    pass\n")


POLICIES_A = "version: 1\npolicies:\n  stale_claim:\n    severity: warning\n"
POLICIES_B = "version: 1\npolicies:\n  stale_claim:\n    severity: error\n"


class CoreProvenanceTests(unittest.TestCase):
    def test_digest_format(self) -> None:
        value = digest("hello")
        self.assertTrue(value.startswith("sha256:"))
        self.assertEqual(len(value), len("sha256:") + 64)

    def test_inventory_hash_is_just_the_digest(self) -> None:
        self.assertEqual(inventory_hash("{}"), digest("{}"))

    def test_digest_is_utf8_stable_for_non_ascii(self) -> None:
        # utf-8 encoding makes the digest stable and platform-independent.
        text = "café — 日本語 — \U0001f600"
        expected = "sha256:" + __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(digest(text), expected)
        self.assertEqual(digest(text), digest(text))

    def test_policy_version_is_key_order_independent(self) -> None:
        a = policy_version({"b": 1, "a": 2})
        b = policy_version({"a": 2, "b": 1})
        self.assertEqual(a, b)

    def test_policy_version_coerces_non_json_values(self) -> None:
        import datetime

        # default=str must not raise on a non-JSON-serializable value.
        value = policy_version({"updated": datetime.date(2026, 6, 18)})
        self.assertTrue(value.startswith("sha256:"))


class ComputeProvenanceTests(unittest.TestCase):
    def test_stable_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)

            self.assertEqual(compute_provenance(repo), compute_provenance(repo))

    def test_matches_inventory_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)

            prov = compute_provenance(repo)
            expected = inventory_hash(render_inventory_json(run_inventory(repo)))
            self.assertEqual(prov["inventory_hash"], expected)

    def test_fact_change_moves_inventory_hash_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)
            before = compute_provenance(repo)

            _write(repo / "src" / "b.py", "def beta():\n    pass\n")
            after = compute_provenance(repo)

            self.assertNotEqual(before["inventory_hash"], after["inventory_hash"])
            self.assertEqual(before["policy_version"], after["policy_version"])

    def test_policy_change_moves_policy_version_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)
            before = compute_provenance(repo)

            _write(repo / ".codas" / "policies.yml", POLICIES_B)
            after = compute_provenance(repo)

            self.assertNotEqual(before["policy_version"], after["policy_version"])
            self.assertEqual(before["inventory_hash"], after["inventory_hash"])


class MalformedConfigProvenanceTests(unittest.TestCase):
    def test_missing_codas_dir_yields_none_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            prov = compute_provenance(repo)
            self.assertIsNone(prov["inventory_hash"])
            self.assertIsNone(prov["policy_version"])

    def test_malformed_policies_only_nulls_policy_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)
            _write(repo / ".codas" / "policies.yml", "version: 1\n  bad: indent\n")

            prov = compute_provenance(repo)

            self.assertIsNone(prov["policy_version"])
            self.assertIsNotNone(prov["inventory_hash"])

    def test_malformed_structure_only_nulls_inventory_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)
            _write(repo / ".codas" / "structure.yml", "version: 1\n  bad: indent\n")

            prov = compute_provenance(repo)

            self.assertIsNone(prov["inventory_hash"])
            self.assertIsNotNone(prov["policy_version"])

    def test_check_json_still_emits_on_malformed_policies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo, POLICIES_A)
            _write(repo / ".codas" / "policies.yml", "version: 1\n  bad: indent\n")

            result = subprocess.run(
                [sys.executable, "-m", "codas", "check", ".", "--json", "--no-exit-code"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env={**__import__("os").environ, "PYTHONPATH": str(Path.cwd() / "src")},
            )
            # provenance must not abort the report: valid JSON, policy-load-error
            # finding present, policy_version null.
            payload = json.loads(result.stdout)
            ids = {f["check_id"] for f in payload["findings"]}
            self.assertIn("policy-load-error", ids)
            self.assertIsNone(payload["provenance"]["policy_version"])


class CheckJsonProvenanceTests(unittest.TestCase):
    def test_check_json_includes_matching_provenance(self) -> None:
        repo = Path.cwd()
        result = subprocess.run(
            [sys.executable, "-m", "codas", "check", ".", "--json"],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertIn("provenance", payload)
        self.assertEqual(payload["provenance"], compute_provenance(repo))


if __name__ == "__main__":
    unittest.main()
