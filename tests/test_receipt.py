from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from codas.app.provenance import compute_provenance
from codas.app.receipt import build_receipt, write_receipt
from codas.core.models import CheckReport, Evidence, Finding
from codas.structure.index import discover_files

FIXED = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _minimal_repo(repo: Path) -> None:
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
    _write(repo / ".codas" / "policies.yml", "version: 1\npolicies: {}\n")
    _write(repo / "docs" / "x.html", '<h2 id="d">d</h2>\n')


def _report(repo: Path, findings: list[Finding] | None = None) -> CheckReport:
    return CheckReport(repo=repo.as_posix(), findings=findings or [])


class BuildReceiptTests(unittest.TestCase):
    def test_deterministic_body_for_fixed_now(self) -> None:
        repo = Path("/tmp/x")
        prov = {"inventory_hash": "sha256:aa", "policy_version": "sha256:bb"}
        a = build_receipt(repo, _report(repo), prov, FIXED).to_json()
        b = build_receipt(repo, _report(repo), prov, FIXED).to_json()

        self.assertEqual(a, b)
        self.assertEqual(a["timestamp"], "2026-06-18T12:00:00Z")
        self.assertEqual(a["kind"], "receipt")
        self.assertEqual(a["provenance"], prov)

    def test_severity_counts_and_ok(self) -> None:
        repo = Path("/tmp/x")
        findings = [
            Finding("error", "e1", "m", [Evidence("a")]),
            Finding("warning", "w1", "m"),
            Finding("warning", "w2", "m"),
        ]
        body = build_receipt(repo, _report(repo, findings), {}, FIXED).to_json()

        self.assertEqual(body["result"], {"ok": False, "error_count": 1, "warning_count": 2})
        self.assertEqual(len(body["findings"]), 3)

    def test_naive_and_offset_now_normalize_to_utc_z(self) -> None:
        repo = Path("/tmp/x")
        naive = datetime(2026, 6, 18, 12, 0, 0)
        offset = datetime(2026, 6, 18, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        a = build_receipt(repo, _report(repo), {}, naive).to_json()["timestamp"]
        b = build_receipt(repo, _report(repo), {}, offset).to_json()["timestamp"]

        self.assertEqual(a, "2026-06-18T12:00:00Z")
        self.assertEqual(b, "2026-06-18T12:00:00Z")


class WriteReceiptTests(unittest.TestCase):
    def test_writes_named_file_with_matching_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo)

            path = write_receipt(repo, _report(repo), now=FIXED)

            self.assertEqual(path.name, "2026-06-18T120000Z.json")
            body = json.loads(path.read_text())
            self.assertEqual(body["provenance"], compute_provenance(repo))
            self.assertTrue(body["result"]["ok"])

    def test_same_second_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo)

            first = write_receipt(repo, _report(repo), now=FIXED)
            second = write_receipt(repo, _report(repo), now=FIXED)

            self.assertNotEqual(first, second)
            self.assertEqual(second.name, "2026-06-18T120000Z-1.json")
            self.assertTrue(first.exists() and second.exists())

    def test_receipts_are_invisible_to_walk_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)  # non-git temp dir -> discover_files walk fallback
            _minimal_repo(repo)
            write_receipt(repo, _report(repo), now=FIXED)

            files = discover_files(repo, (".",))

            self.assertFalse(any(f.startswith(".codas/receipts/") for f in files))


class CheckReceiptCliTests(unittest.TestCase):
    def test_check_receipt_flag_writes_and_json_stays_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo)
            env = {**__import__("os").environ, "PYTHONPATH": str(Path.cwd() / "src")}

            result = subprocess.run(
                # --no-exit-code: the minimal fixture may have findings; this test is
                # about receipt writing + JSON integrity, not the pass/fail result.
                [sys.executable, "-m", "codas", "check", ".", "--json", "--receipt", "--no-exit-code"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)  # --receipt must not corrupt JSON
            self.assertIn("receipt", payload)
            self.assertTrue(Path(payload["receipt"]).exists())

    def test_check_without_flag_writes_no_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _minimal_repo(repo)
            env = {**__import__("os").environ, "PYTHONPATH": str(Path.cwd() / "src")}

            subprocess.run(
                [sys.executable, "-m", "codas", "check", "."],
                cwd=repo, text=True, capture_output=True, check=False, env=env,
            )

            self.assertFalse((repo / ".codas" / "receipts").exists())


if __name__ == "__main__":
    unittest.main()
