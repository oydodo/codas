from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from codas.app.book import (
    BOOK_ROOT,
    _read_chapter_prose,
    _strip_claims_block,
    book_pages,
    project_book,
    verify_book,
    write_book,
)
from codas.app.inventory import run_inventory

# Codas's configured product scope (.codas/config.yml wiki.product_roots) — the direct
# project_book unit tests pass it so they exercise the REAL book scope, not the generic
# ("src",) default (which would add a repo-root chapter).
# KEEP IN SYNC with .codas/config.yml `wiki.product_roots` (no assertion ties them).
CODAS_ROOTS = ("src/codas",)


class ProjectBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = run_inventory(Path.cwd())
        cls.pages = project_book(cls.inventory, None, CODAS_ROOTS)

    def test_pages_present(self) -> None:
        self.assertIn(f"{BOOK_ROOT}/index.md", self.pages)
        self.assertIn(f"{BOOK_ROOT}/codas-app.md", self.pages)

    def test_projection_is_deterministic(self) -> None:
        again = project_book(self.inventory, None, CODAS_ROOTS)
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
        self.assertEqual(project_book(mutated, None, CODAS_ROOTS), self.pages)

    def test_chapter_set_is_derived_code_units_only(self) -> None:
        # W4b: the chapter set is DERIVED from tree-node ownership — every code unit gets a
        # chapter; non-code units (own no symbols) get NONE.
        chapter_files = {p for p in self.pages if p != f"{BOOK_ROOT}/index.md"}
        # several code units beyond codas-app are now rendered...
        for code_unit in ("codas-app", "codas-policies", "codas-facts", "codas-adapters"):
            self.assertIn(f"{BOOK_ROOT}/{code_unit}.md", chapter_files)
        # ...and non-code units (config/docs/tasks) are NOT rendered as chapters.
        for non_code in ("program-plan", "agents-guide", "codas-docs", "trellis-workflow"):
            self.assertNotIn(f"{BOOK_ROOT}/{non_code}.md", chapter_files)
            self.assertNotIn(f"[{non_code}](", self.pages[f"{BOOK_ROOT}/index.md"])

    def test_every_chapter_has_banner_and_owner(self) -> None:
        # Each rendered chapter (not the index) carries the open-world banner exactly once.
        for page, content in self.pages.items():
            if page == f"{BOOK_ROOT}/index.md":
                continue
            self.assertEqual(content.count("**Open-world.**"), 1, page)
            self.assertIn("- **Owner:**", content)


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


class ProseWeaveTests(unittest.TestCase):
    """W6: authored .codas/wiki/code/<unit>.md prose woven into the chapter as ## Overview."""

    def setUp(self) -> None:
        self.inventory = run_inventory(Path.cwd())

    def test_overview_present_when_prose_given(self) -> None:
        prose = "The **why**: this subsystem is the boundary seam."
        pages = project_book(self.inventory, {"codas-app": prose}, CODAS_ROOTS)
        chapter = pages[f"{BOOK_ROOT}/codas-app.md"]
        self.assertIn("## Overview", chapter)
        self.assertIn("boundary seam", chapter)
        # Overview sits before the structure; banner still rendered exactly once.
        self.assertLess(chapter.index("## Overview"), chapter.index("## Modules & symbols"))
        self.assertEqual(chapter.count("**Open-world.**"), 1)

    def test_no_overview_when_no_prose(self) -> None:
        # A unit with no source page renders the skeleton — no Overview, no dead section.
        pages = project_book(self.inventory, {}, CODAS_ROOTS)
        self.assertNotIn("## Overview", pages[f"{BOOK_ROOT}/codas-app.md"])

    def test_strip_claims_block(self) -> None:
        text = "# title\n\nprose body\n\n```atlas:claims\ndefines: c -> a/b.py::::f\n```\n"
        self.assertEqual(_strip_claims_block(text), "# title\n\nprose body")
        # a claims-only page weaves nothing
        self.assertEqual(_strip_claims_block("```atlas:claims\ncontains: a/b.py\n```\n"), "")

    def test_read_chapter_prose_missing_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_read_chapter_prose(Path(d), "nope"), "")

    def test_prose_content_edit_is_out_of_hash(self) -> None:
        # The .codas/wiki/code/ prose CONTENT is excluded from the inventory hash, so EDITING a
        # chapter's prose must NOT move `codas inventory` (the book restales; the hash does not).
        # NB the file's EXISTENCE is a real artifact fact (a new page changes artifact_count) —
        # this isolates the content-out-of-hash property by editing an existing page in place.
        from codas.structure.inventory import build_inventory

        repo = Path.cwd()
        page = repo / ".codas" / "wiki" / "code" / "_w6_probe.md"
        try:
            page.write_text("# probe\n\nprose ONE\n", encoding="utf-8")
            a = json.dumps(build_inventory(repo), sort_keys=True)
            page.write_text("# probe\n\nCOMPLETELY different prose TWO\n", encoding="utf-8")
            b = json.dumps(build_inventory(repo), sort_keys=True)
        finally:
            page.unlink()
        self.assertEqual(a, b)  # content changed, inventory identical


class LatentLeakGuardTests(unittest.TestCase):
    def test_no_governance_claim_targets_the_book(self) -> None:
        # W7 CLOSED the leak: a governance claim under the book root now resolves exists=False
        # (config-aware, see BookReferenceLeakClosedTests). This guard remains as a hygiene
        # check that Codas's OWN committed docs don't (yet) reference the rendered book — if one
        # ever does it should appear with exists=False, never perturbing the hash; the active
        # closure is proven below. A non-empty result here is a heads-up, not a leak.
        from codas.structure.inventory import build_inventory

        inv = build_inventory(Path.cwd())
        sections = (
            (inv.get("doc_claims") or {}).get("references") or [],
            (inv.get("wiki_claims") or {}).get("claims") or [],
            (inv.get("html_claims") or {}).get("references") or [],
        )
        book_refs = [
            c
            for section in sections
            for c in section
            if str(c.get("path", "")).startswith(f"{BOOK_ROOT}/")
        ]
        # Whatever the count, NONE may carry exists=True (that would be the leak re-opening).
        leaked = [c["path"] for c in book_refs if c.get("exists")]
        self.assertEqual(
            leaked,
            [],
            f"governance claim(s) under {BOOK_ROOT}/ resolved exists=True — the W7 existence "
            f"guard is bypassed somewhere: {leaked}",
        )


class BookReferenceLeakClosedTests(unittest.TestCase):
    """W7 R2/R3: a governance doc referencing the rendered book resolves exists=False and the
    inventory is byte-identical whether or not the book is on disk (the leak is CLOSED), while
    an explicit opt-out (`wiki.book_root: ""`) governs a real `wiki/` dir normally."""

    # A single non-catch-all unit (owns `src` only) so a SCANNED wiki/ file surfaces as
    # `unowned` — the signal that distinguishes "reserved" (invisible) from "governed".
    _STRUCTURE = (
        "version: 1\n"
        "kind: structure_map\n"
        "units:\n"
        "  code:\n"
        "    path: src\n"
        "    kind: package\n"
        "    owner: O\n"
        "    purpose: x\n"
        "    canonical_placement: x\n"
    )

    def _scaffold(self, repo: Path, book_root: str, with_book: bool) -> None:
        (repo / ".codas").mkdir(parents=True, exist_ok=True)
        (repo / ".codas" / "config.yml").write_text(
            f'version: 1\nwiki:\n  book_root: "{book_root}"\n', encoding="utf-8"
        )
        (repo / ".codas" / "structure.yml").write_text(self._STRUCTURE, encoding="utf-8")
        # A supporting governance doc that references the rendered book (link + code span).
        (repo / "README.md").write_text(
            f"# r\n\nSee [the book]({BOOK_ROOT}/index.md) and `{BOOK_ROOT}/codas-app.md`.\n",
            encoding="utf-8",
        )
        if with_book:
            (repo / BOOK_ROOT).mkdir(parents=True, exist_ok=True)
            (repo / BOOK_ROOT / "index.md").write_text("# book\n", encoding="utf-8")
            (repo / BOOK_ROOT / "codas-app.md").write_text("# chapter\n", encoding="utf-8")

    def _book_refs(self, inv: dict) -> list[dict]:
        return [
            r
            for r in (inv.get("doc_claims") or {}).get("references") or []
            if str(r["path"]).startswith(f"{BOOK_ROOT}/")
        ]

    def test_book_reference_does_not_move_inventory(self) -> None:
        from codas.structure.inventory import build_inventory

        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            present, absent = Path(a), Path(b)
            self._scaffold(present, "wiki", with_book=True)
            self._scaffold(absent, "wiki", with_book=False)
            inv_present = build_inventory(present)
            inv_absent = build_inventory(absent)

            # the README's book references are scanned (real doc claims)...
            refs = self._book_refs(inv_present)
            self.assertEqual({r["path"] for r in refs}, {"wiki/index.md", "wiki/codas-app.md"})
            # ...but resolve exists=False DESPITE the book being on disk (the guard fires).
            self.assertTrue(all(r["exists"] is False for r in refs), refs)
            # and the book's on-disk presence does not move the inventory at all.
            self.assertEqual(
                json.dumps(inv_present, sort_keys=True),
                json.dumps(inv_absent, sort_keys=True),
            )

    def test_opt_out_governs_real_wiki_dir(self) -> None:
        # R3: `book_root: ""` disables the reservation — the `wiki/` dir is scanned normally and
        # a doc reference to it resolves exists=True (no over-reach onto a user's real docs).
        from codas.structure.inventory import build_inventory

        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            self._scaffold(repo, "", with_book=True)
            inv = build_inventory(repo)
            refs = self._book_refs(inv)
            self.assertTrue(refs)
            self.assertTrue(all(r["exists"] is True for r in refs), refs)
            # the wiki/ files are now part of the scanned set (governed, not reserved).
            self.assertIn("wiki/index.md", inv.get("unowned") or [])


if __name__ == "__main__":
    unittest.main()
