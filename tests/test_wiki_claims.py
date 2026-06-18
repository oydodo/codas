from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codas.adapters.wiki import extract_wiki_claims

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


INDEX_MD = """# Wiki

## Canonical Sources

- `docs/real.html`: a real file.
- `src/`: a directory.
- `scripts/run`: an extensionless script.
- `data/**`: a glob.
- `docs/gone.html`: a missing file.

## Concepts

- [Foo](concepts/foo.md)

## Bootstrap Rule

```bash
- `not/a/claim.py`
```
"""

FOO_MD = """# Foo

## Canonical Definition

Prose.

Evidence:

- `docs/real.html`
- `src/`

## Required Synchronization

When Foo changes, update:

- `.codas/structure.yml`
"""


def _fixture(repo: Path) -> None:
    _write(repo / ".codas" / "wiki" / "index.md", INDEX_MD)
    _write(repo / ".codas" / "wiki" / "concepts" / "foo.md", FOO_MD)
    _write(repo / "docs" / "real.html", "<p>real</p>\n")
    _write(repo / "src" / "mod.py", "x = 1\n")
    _write(repo / "scripts" / "run", "#!/bin/sh\n")
    _write(repo / "data" / "x.txt", "data\n")


def _files(repo: Path) -> tuple[str, ...]:
    found = []
    for path in repo.rglob("*.md"):
        found.append(path.relative_to(repo).as_posix())
    return tuple(sorted(found))


def _tuples(repo: Path):
    claims = extract_wiki_claims(repo, _files(repo)).claims
    return [(c.concept, c.kind, c.path, c.path_kind, c.exists) for c in claims]


class ExtractWikiClaimsTests(unittest.TestCase):
    def test_kinds_paths_and_existence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)

            got = set(_tuples(repo))

            # canonical_source: real file, directory, extensionless, glob, missing
            self.assertIn(("index", "canonical_source", "docs/real.html", "literal", True), got)
            self.assertIn(("index", "canonical_source", "src", "literal", True), got)
            self.assertIn(("index", "canonical_source", "scripts/run", "literal", True), got)
            self.assertIn(("index", "canonical_source", "data/**", "glob", True), got)
            self.assertIn(("index", "canonical_source", "docs/gone.html", "literal", False), got)
            # concept_page link (source-relative resolution)
            self.assertIn(
                ("index", "concept_page", ".codas/wiki/concepts/foo.md", "literal", True), got
            )
            # evidence (under the Evidence: label) on the concept page
            self.assertIn(("foo", "evidence", "docs/real.html", "literal", True), got)
            self.assertIn(("foo", "evidence", "src", "literal", True), got)
            # sync_target under Required Synchronization (missing target -> exists False)
            self.assertIn(("foo", "sync_target", ".codas/structure.yml", "literal", False), got)

    def test_fence_aware(self) -> None:
        # `not/a/claim.py` sits inside the Bootstrap Rule fenced block -> ignored.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            paths = {c.path for c in extract_wiki_claims(repo, _files(repo)).claims}
            self.assertNotIn("not/a/claim.py", paths)

    def test_scoped_to_wiki_root(self) -> None:
        # A Canonical Sources section in a NON-wiki .md yields no wiki claim.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            _write(
                repo / "notes" / "README.md",
                "## Canonical Sources\n\n- `docs/real.html`\n",
            )
            sources = {c.source for c in extract_wiki_claims(repo, _files(repo)).claims}
            self.assertNotIn("notes/README.md", sources)

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _fixture(repo)
            self.assertEqual(
                extract_wiki_claims(repo, _files(repo)),
                extract_wiki_claims(repo, _files(repo)),
            )

    def test_prose_slash_span_dropped(self) -> None:
        # A slashed backtick span that has no extension, is not a glob, and does
        # not resolve on disk is prose, not a path claim -> dropped.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "wiki" / "index.md",
                "## Canonical Sources\n\n- `read/write`: prose, not a path.\n",
            )
            paths = {c.path for c in extract_wiki_claims(repo, _files(repo)).claims}
            self.assertNotIn("read/write", paths)

    def test_malformed_glob_does_not_crash(self) -> None:
        # `docs/**.md` is an invalid glob (`**` not a whole component) -> Path.glob
        # raises ValueError. The parser must record it as not-found, never crash.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "wiki" / "index.md",
                "## Canonical Sources\n\n- `docs/**.md`: a malformed glob.\n",
            )
            claims = extract_wiki_claims(repo, _files(repo)).claims
            glob = [c for c in claims if c.path == "docs/**.md"]
            self.assertEqual(len(glob), 1)
            self.assertEqual(glob[0].path_kind, "glob")
            self.assertFalse(glob[0].exists)

    def test_wrong_role_refs_ignored(self) -> None:
        # concept_page is asserted by links only; the path-list kinds by code spans
        # only. A code span under `## Concepts` and a link under `Evidence:` are the
        # wrong role and must be ignored.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "docs" / "real.html", "<p>x</p>\n")
            _write(
                repo / ".codas" / "wiki" / "index.md",
                "## Concepts\n\n- `concepts/foo.md`\n",  # code span, wrong role
            )
            _write(
                repo / ".codas" / "wiki" / "concepts" / "foo.md",
                "Evidence:\n\n- [real](docs/real.html)\n",  # link, wrong role
            )
            claims = extract_wiki_claims(repo, _files(repo)).claims
            self.assertEqual(
                [c for c in claims if c.kind == "concept_page"], []
            )
            self.assertEqual([c for c in claims if c.kind == "evidence"], [])

    def test_missing_concept_link_is_not_a_wiki_finding(self) -> None:
        # A broken concept-page link is recorded as a wiki_claim with exists=False,
        # but D1 emits NO finding (no policy). The existing stale_claim policy, via
        # doc_claims, is what would flag the broken link -- not wiki_claims. This
        # test pins the facts-only contract: the parser records, never judges.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "wiki" / "index.md",
                "## Concepts\n\n- [Gone](concepts/gone.md)\n",
            )
            claims = extract_wiki_claims(repo, _files(repo)).claims
            link = [c for c in claims if c.kind == "concept_page"]
            self.assertEqual(len(link), 1)
            self.assertFalse(link[0].exists)


class WikiClaimsInventorySmokeTests(unittest.TestCase):
    def _inventory_json(self) -> str:
        env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        result = subprocess.run(
            [sys.executable, "-m", "codas", "inventory", ".", "--json"],
            cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_repo_inventory_has_wiki_claims_block(self) -> None:
        out = self._inventory_json()
        inventory = json.loads(out)
        self.assertIn("wiki_claims", inventory)
        claims = inventory["wiki_claims"]["claims"]
        self.assertTrue(claims)
        kinds = {c["kind"] for c in claims}
        self.assertIn("canonical_source", kinds)
        self.assertIn("evidence", kinds)
        # the real index.md cites the `.trellis/tasks/**` glob
        self.assertIn("glob", {c["path_kind"] for c in claims})

    def test_repo_inventory_byte_identical(self) -> None:
        self.assertEqual(self._inventory_json(), self._inventory_json())

    def test_repo_check_stays_clean(self) -> None:
        # D1 is facts-only: adding wiki_claims must not introduce any finding.
        env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        result = subprocess.run(
            [sys.executable, "-m", "codas", "check", "."],
            cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
