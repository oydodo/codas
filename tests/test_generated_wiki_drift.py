from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.adapters.wiki import extract_generated_claims
from codas.app.check import run_check
from codas.config.loader import CodasConfig
from codas.facts.context import ScanContext
from codas.policies.generated_wiki_drift import check_generated_wiki_drift

STRUCTURE = """\
version: 1
kind: structure_map
units:
  u-a:
    path: src/a
    kind: package
    owner: Owner A
    purpose: p
    canonical_placement: c
  u-b:
    path: src/b
    kind: package
    owner: Owner B
    purpose: p
    canonical_placement: c
"""

PROGRAM = """\
version: 1
kind: program_plan
work_items:
  - id: program:P0:x
    phase: P0
    title: X
    status: completed
"""

CORRECT = (
    "source_inventory_hash: sha256:test\n"
    "unit: u-a -> src/a\n"
    "unit: u-b -> src/b\n"
    "roadmap: program:P0:x -> completed\n"
)

PAGE_REL = ".codas/wiki/generated/governance.md"


def _page(body: str | None) -> str:
    head = "# Generated\n\nprose line\n\n## Structure Units\n\n| u | p |\n"
    if body is None:
        return head  # no atlas:claims block
    return head + "\n```atlas:claims\n" + body + "```\n"


def _ctx(directory: str, page_text: str, *, structure: bool = True) -> ScanContext:
    repo = Path(directory)
    (repo / ".codas").mkdir(parents=True, exist_ok=True)
    if structure:
        (repo / ".codas" / "structure.yml").write_text(STRUCTURE)
    (repo / ".codas" / "program.yml").write_text(PROGRAM)
    gen = repo / ".codas" / "wiki" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "governance.md").write_text(page_text)
    config = CodasConfig(
        path=repo / ".codas" / "config.yml", raw={"wiki": {"path": ".codas/wiki"}}
    )
    return ScanContext(repo=repo, config=config, roots=(), files=(PAGE_REL,))


def _ids(findings):
    return [f.check_id for f in findings]


class ExtractGeneratedClaimsTests(unittest.TestCase):
    def test_parses_hash_and_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            page = repo / ".codas" / "wiki" / "generated" / "g.md"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(
                _page(CORRECT)
                + "\n```python\nunit: not-a-claim -> x\n```\n"  # other fence ignored
            )
            claims = extract_generated_claims(
                repo, (".codas/wiki/generated/g.md",)
            )
            page0 = claims.pages[0]
            self.assertTrue(page0.has_block)
            self.assertEqual(page0.source_inventory_hash, "sha256:test")
            kinds = [(c.kind, c.subject, c.value) for c in page0.claims]
            self.assertIn(("unit", "u-a", "src/a"), kinds)
            self.assertIn(("roadmap", "program:P0:x", "completed"), kinds)
            self.assertNotIn(("unit", "not-a-claim", "x"), kinds)  # other fence skipped

    def test_no_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            page = repo / ".codas" / "wiki" / "generated" / "g.md"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(_page(None))
            page0 = extract_generated_claims(
                repo, (".codas/wiki/generated/g.md",)
            ).pages[0]
            self.assertFalse(page0.has_block)
            self.assertEqual(page0.claims, ())

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            page = repo / ".codas" / "wiki" / "generated" / "g.md"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(_page(CORRECT))
            files = (".codas/wiki/generated/g.md",)
            self.assertEqual(
                extract_generated_claims(repo, files),
                extract_generated_claims(repo, files),
            )


class CheckGeneratedWikiDriftTests(unittest.TestCase):
    def test_correct_page_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(check_generated_wiki_drift(_ctx(directory, _page(CORRECT))), [])

    def test_bogus_unit_path(self) -> None:
        body = "source_inventory_hash: sha256:t\nunit: u-a -> WRONG\n"
        with tempfile.TemporaryDirectory() as directory:
            findings = check_generated_wiki_drift(_ctx(directory, _page(body)))
            self.assertEqual(_ids(findings), ["generated-wiki-drift"])
            self.assertIn("u-a", findings[0].message)

    def test_unknown_unit(self) -> None:
        body = "source_inventory_hash: sha256:t\nunit: u-z -> src/z\n"
        with tempfile.TemporaryDirectory() as directory:
            findings = check_generated_wiki_drift(_ctx(directory, _page(body)))
            self.assertEqual(len(findings), 1)
            self.assertIn("unknown", findings[0].message)

    def test_roadmap_status_mismatch(self) -> None:
        body = "source_inventory_hash: sha256:t\nroadmap: program:P0:x -> planned\n"
        with tempfile.TemporaryDirectory() as directory:
            findings = check_generated_wiki_drift(_ctx(directory, _page(body)))
            self.assertEqual(len(findings), 1)
            self.assertIn("planned", findings[0].message)

    def test_missing_block_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            findings = check_generated_wiki_drift(_ctx(directory, _page(None)))
            self.assertEqual(len(findings), 1)
            self.assertIn("atlas:claims", findings[0].message)

    def test_missing_hash_is_error(self) -> None:
        body = "unit: u-a -> src/a\n"  # claims but no source_inventory_hash
        with tempfile.TemporaryDirectory() as directory:
            findings = check_generated_wiki_drift(_ctx(directory, _page(body)))
            self.assertEqual(len(findings), 1)

    def test_loader_failure_skips_kind(self) -> None:
        # No structure.yml -> _unit_paths is None -> a bogus unit claim is SKIPPED, not
        # flagged (no cascade); the roadmap claim is still verified.
        body = "source_inventory_hash: sha256:t\nunit: u-z -> bad\nroadmap: program:P0:x -> completed\n"
        with tempfile.TemporaryDirectory() as directory:
            findings = check_generated_wiki_drift(
                _ctx(directory, _page(body), structure=False)
            )
            self.assertEqual(findings, [])

    def test_real_repo_clean(self) -> None:
        report = run_check(Path.cwd())
        drift = [f for f in report.findings if f.check_id == "generated-wiki-drift"]
        self.assertEqual(drift, [])


if __name__ == "__main__":
    unittest.main()
