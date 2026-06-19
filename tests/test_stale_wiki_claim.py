from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import load_codas_config
from codas.facts.context import build_scan_context
from codas.policies.stale_wiki_claim import check_stale_wiki_claim

REPO_ROOT = Path(__file__).resolve().parents[1]

CONFIG = """\
version: 1
constraint_sources:
  authoritative:
    - docs/design.html
    - specs/**/*.md
  supporting:
    - AGENTS.md
workflow:
  adapter: trellis
  root: .trellis
  task_globs:
    - .trellis/tasks/*/task.json
dogfooding:
  protocol: docs/design.html#d
"""

INDEX_MD = """# Wiki

## Canonical Sources

- `docs/design.html`: declared authoritative (exact).
- `specs/sub/x.md`: matched by the specs/**/*.md glob.
- `docs/rogue.html`: NOT a declared constraint source.
- `data/**`: a glob canonical source (authority-exempt).

## Concepts

- [Foo](concepts/foo.md)
"""

REAL_MD = """# Real

Evidence:

- `docs/design.html`
- `docs/missing.html`

## Required Synchronization

- `gone/x.md`
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fixture(repo: Path) -> None:
    _write(repo / ".codas" / "config.yml", CONFIG)
    _write(repo / ".codas" / "wiki" / "index.md", INDEX_MD)
    _write(repo / ".codas" / "wiki" / "concepts" / "real.md", REAL_MD)
    _write(repo / "docs" / "design.html", "<p>d</p>\n")
    _write(repo / "specs" / "sub" / "x.md", "x\n")
    _write(repo / "docs" / "rogue.html", "<p>r</p>\n")  # exists -> only authority fires
    _write(repo / "data" / "y.txt", "y\n")  # makes data/** glob exist


def _findings(repo: Path):
    config = load_codas_config(repo / ".codas" / "config.yml")
    ctx = build_scan_context(repo, config)
    return check_stale_wiki_claim(ctx)


class StaleWikiClaimTests(unittest.TestCase):
    def test_expected_findings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            findings = _findings(repo)
            messages = sorted(f.message for f in findings)

            # Exactly three: one authority (rogue), two existence (evidence, sync).
            self.assertEqual(len(findings), 3, messages)
            self.assertTrue(all(f.check_id == "stale-wiki-claim" for f in findings))
            self.assertTrue(all(f.severity == "warning" for f in findings))

            joined = "\n".join(messages)
            self.assertIn("does not declare authoritative or supporting: docs/rogue.html", joined)
            self.assertIn("evidence claim references a missing path: docs/missing.html", joined)
            self.assertIn("sync_target claim references a missing path: gone/x.md", joined)

            # Verified claims never appear: exact + glob-matched authority, the
            # authority-exempt glob, the concept_page link, the existing evidence.
            self.assertNotIn("docs/design.html", joined)
            self.assertNotIn("specs/sub/x.md", joined)
            self.assertNotIn("data/**", joined)
            self.assertNotIn("concepts/foo.md", joined)

    def test_literal_matched_by_config_glob_passes_authority(self) -> None:
        # `specs/sub/x.md` is matched by the config glob `specs/**/*.md` (fnmatch
        # `*` spans `/`) -> verified, no authority finding.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            paths = {f.evidence[0].detail for f in _findings(repo)}
            self.assertNotIn("specs/sub/x.md", paths)

    def test_glob_canonical_source_is_authority_exempt(self) -> None:
        # `data/**` is a glob canonical source absent from config; it must NOT raise
        # an authority finding (existence-only, and it exists here).
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            paths = {f.evidence[0].detail for f in _findings(repo)}
            self.assertNotIn("data/**", paths)

    def test_concept_page_link_not_flagged(self) -> None:
        # A broken concept_page link is left to stale_claim (links) -> no
        # stale-wiki-claim finding for it.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)  # concepts/foo.md never created -> link is broken
            paths = {f.evidence[0].detail for f in _findings(repo)}
            self.assertNotIn("concepts/foo.md", paths)

    def test_unauthorized_and_missing_canonical_source_emits_two_findings(self) -> None:
        # A literal canonical_source that is BOTH not a declared constraint source
        # AND missing on disk is two distinct defects -> two findings on one claim,
        # ordered stably by the message tie-break (authority sorts before "missing").
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "config.yml", CONFIG)
            _write(
                repo / ".codas" / "wiki" / "index.md",
                "## Canonical Sources\n\n- `docs/ghost.html`: unauthorized and missing.\n",
            )
            findings = _findings(repo)
            self.assertEqual(len(findings), 2, [f.message for f in findings])
            self.assertTrue(all(f.evidence[0].detail == "docs/ghost.html" for f in findings))
            messages = [f.message for f in findings]
            self.assertTrue(any("does not declare" in m for m in messages))
            self.assertTrue(any("missing path" in m for m in messages))
            # deterministic, total sort: re-running yields the identical order.
            self.assertEqual(messages, [f.message for f in _findings(repo)])

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            self.assertEqual(_findings(repo), _findings(repo))

    def test_clean_on_this_repo(self) -> None:
        # Dogfood: the real repo's wiki claims all verify -> zero findings.
        config = load_codas_config(REPO_ROOT / ".codas" / "config.yml")
        ctx = build_scan_context(REPO_ROOT, config)
        self.assertEqual(check_stale_wiki_claim(ctx), [])


if __name__ == "__main__":
    unittest.main()
