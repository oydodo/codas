from __future__ import annotations

import copy
import unittest
from pathlib import Path

from codas.app.book import (
    BOOK_ROOT,
    book_pages,
    project_book,
    verify_book,
    write_book,
)
from codas.app.inventory import run_inventory


class ProjectBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = run_inventory(Path.cwd())
        cls.pages = project_book(cls.inventory)

    def test_pages_present(self) -> None:
        self.assertIn(f"{BOOK_ROOT}/index.md", self.pages)
        self.assertIn(f"{BOOK_ROOT}/codas-app.md", self.pages)

    def test_projection_is_deterministic(self) -> None:
        again = project_book(self.inventory)
        self.assertEqual(self.pages, again)

    def test_index_links_chapter_unit_and_lists_others_plain(self) -> None:
        index = self.pages[f"{BOOK_ROOT}/index.md"]
        # the rendered chapter is a live link...
        self.assertIn("[codas-app](codas-app.md)", index)
        # ...a non-chapter unit is listed plain (no link), no dead links.
        self.assertIn("| codas-docs |", index)
        self.assertNotIn("[codas-docs](", index)

    def test_chapter_has_banner_once_tree_and_mermaid(self) -> None:
        chapter = self.pages[f"{BOOK_ROOT}/codas-app.md"]
        self.assertEqual(chapter.count("**Open-world.**"), 1)  # caveat rendered exactly once
        self.assertIn("## Modules & symbols", chapter)
        self.assertIn("```mermaid", chapter)
        self.assertIn("graph LR", chapter)
        # a real product symbol from this unit appears in the tree-slice
        self.assertIn("`run_inventory`", chapter)
        # no external script / CDN (matches the S1 self-contained rule)
        self.assertNotIn("<script", chapter)

    def test_renders_only_stable_fields(self) -> None:
        # Mutating a VOLATILE observation (artifact_count) must NOT change the rendered book —
        # the book pins exactly when its SOURCE facts move, never on unrelated churn (codex Q2).
        mutated = copy.deepcopy(self.inventory)
        for unit in mutated.get("units") or []:
            unit.setdefault("observed", {})["artifact_count"] = 999_999
        self.assertEqual(project_book(mutated), self.pages)

    def test_absent_chapter_unit_skipped_not_crash(self) -> None:
        # A configured chapter unit absent from THIS repo is skipped (renders on any repo);
        # the index links only the chapters actually rendered (no dead link).
        from codas.app import book

        original = book._CHAPTER_UNITS
        book._CHAPTER_UNITS = ("does-not-exist", "codas-app")
        try:
            pages = project_book(self.inventory)
        finally:
            book._CHAPTER_UNITS = original
        self.assertNotIn(f"{BOOK_ROOT}/does-not-exist.md", pages)
        self.assertIn(f"{BOOK_ROOT}/codas-app.md", pages)
        self.assertNotIn("[does-not-exist](", pages[f"{BOOK_ROOT}/index.md"])


class WriteVerifyBookTests(unittest.TestCase):
    def test_write_is_idempotent_and_verify_clean(self) -> None:
        repo = Path.cwd()
        write_book(repo)
        self.assertEqual(verify_book(repo), [])  # fresh render == on disk
        write_book(repo)  # re-write
        self.assertEqual(verify_book(repo), [])  # still byte-identical

    def test_verify_detects_handedit(self) -> None:
        repo = Path.cwd()
        write_book(repo)
        page = next(iter(book_pages(repo)))
        original = page.read_bytes()
        try:
            page.write_bytes(original + b"\nhand edit\n")
            self.assertIn(page, verify_book(repo))
        finally:
            page.write_bytes(original)  # restore committed bytes
        self.assertEqual(verify_book(repo), [])

    def test_verify_detects_orphan_page(self) -> None:
        # A committed wiki/*.md no longer rendered must be flagged (regenerate won't remove it).
        repo = Path.cwd()
        write_book(repo)
        orphan = repo / "wiki" / "_orphan_test.md"
        try:
            orphan.write_bytes(b"stale chapter\n")
            self.assertIn(orphan, verify_book(repo))
        finally:
            orphan.unlink()
        self.assertEqual(verify_book(repo), [])


class LatentLeakGuardTests(unittest.TestCase):
    def test_no_governance_claim_targets_the_book(self) -> None:
        # The wiki/ book is excluded at the FILE SCANNER, but the doc/wiki/html claim adapters
        # resolve claim-target existence by hitting the filesystem directly. So IF a governance
        # doc ever references a path under the committed book, its `exists` flips on the book's
        # presence and bleeds into the byte-identical inventory hash. That fix is deferred to
        # W7 (config-aware book root — a blanket "wiki/ absent" rule over-reaches onto a user's
        # real wiki/ docs). This guard FAILS the moment that latent leak activates, forcing the
        # W7 existence fix to land alongside the reference.
        from codas.structure.inventory import build_inventory

        inv = build_inventory(Path.cwd())
        sections = (
            (inv.get("doc_claims") or {}).get("references") or [],
            (inv.get("wiki_claims") or {}).get("claims") or [],
            (inv.get("html_claims") or {}).get("references") or [],
        )
        offenders = [
            c["path"]
            for section in sections
            for c in section
            if str(c.get("path", "")).startswith(f"{BOOK_ROOT}/")
        ]
        self.assertEqual(
            offenders,
            [],
            f"governance claim(s) reference the derived {BOOK_ROOT}/ book — activate the W7 "
            f"config-aware existence fix before this lands: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
