from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.facts.context import ScanContext, build_scan_context
from codas.policies.stale_claim import check_stale_claim


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _ctx(repo: Path) -> ScanContext:
    return build_scan_context(repo, _config(repo))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class StaleClaimPolicyTests(unittest.TestCase):
    def test_broken_link_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "doc.md", "See [the design](missing.md) for details.\n")

            findings = check_stale_claim(_ctx(repo))

            self.assertEqual(len(findings), 1)
            finding = findings[0]
            self.assertEqual(finding.check_id, "stale-claim")
            self.assertEqual(finding.severity, "warning")
            self.assertEqual(finding.evidence[0].path, "doc.md")
            self.assertEqual(finding.evidence[0].line, 1)
            self.assertEqual(finding.evidence[0].detail, "missing.md")

    def test_existing_link_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "real.md", "target\n")
            _write(repo / "doc.md", "See [real](real.md).\n")

            self.assertEqual(check_stale_claim(_ctx(repo)), [])

    def test_code_span_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            # has slash + ext so the adapter indexes it as a kind=code claim,
            # but stale_claim is link-only and must not flag it.
            _write(repo / "doc.md", "Mentions `sub/missing.md` in prose.\n")

            self.assertEqual(check_stale_claim(_ctx(repo)), [])

    def test_external_link_and_image_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / "doc.md",
                "[site](https://example.com) and ![pic](missing.png)\n",
            )

            self.assertEqual(check_stale_claim(_ctx(repo)), [])

    def test_findings_are_sorted_by_source_then_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "b.md", "[x](gone_b.md)\n")
            _write(repo / "a.md", "line one\n[x](gone_a.md)\n")

            findings = check_stale_claim(_ctx(repo))

            self.assertEqual(
                [(f.evidence[0].path, f.evidence[0].line) for f in findings],
                [("a.md", 2), ("b.md", 1)],
            )


if __name__ == "__main__":
    unittest.main()
