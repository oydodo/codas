from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.adapters.html import extract_html_claims, governed_html_files
from codas.adapters.markdown import DocClaim
from codas.config.loader import load_codas_config
from codas.facts.context import ScanContext
from codas.policies.stale_html_claim import check_stale_html_claim

REPO = Path(__file__).resolve().parents[1]


class GovernedHtmlFiles(unittest.TestCase):
    def test_literal_match(self) -> None:
        files = ("docs/a.html", "docs/b.html", "src/x.py")
        self.assertEqual(governed_html_files(files, ("docs/a.html",)), ["docs/a.html"])

    def test_glob_match(self) -> None:
        files = ("docs/a.html", "docs/sub/c.html", "notes/n.html")
        got = governed_html_files(files, ("docs/**/*.html", "docs/*.html"))
        self.assertEqual(got, ["docs/a.html", "docs/sub/c.html"])

    def test_non_html_and_ungoverned_excluded(self) -> None:
        files = ("docs/a.html", "docs/a.md", "vendor/r.html")
        self.assertEqual(governed_html_files(files, ("docs/*.html",)), ["docs/a.html"])

    def test_leading_dot_slash_in_pattern_normalized(self) -> None:
        files = ("docs/a.html",)
        self.assertEqual(governed_html_files(files, ("./docs/a.html",)), ["docs/a.html"])

    def test_empty_patterns_governs_nothing(self) -> None:
        self.assertEqual(governed_html_files(("docs/a.html",), ()), [])


class ExtractHtmlClaims(unittest.TestCase):
    def _extract(self, html: str, extra: tuple[str, ...] = ()) -> tuple[list[DocClaim], Path]:
        d = tempfile.mkdtemp()
        repo = Path(d)
        (repo / "docs").mkdir()
        (repo / "docs" / "spec.html").write_text(html)
        for rel in extra:
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")
        return extract_html_claims(repo, ["docs/spec.html"]), repo

    def test_inline_code_path_existing_and_missing(self) -> None:
        html = (
            "<p>real <code>docs/spec.html</code> and "
            "gone <code>docs/missing.md</code></p>"
        )
        claims, _ = self._extract(html)
        by_path = {c.path: c for c in claims}
        self.assertIn("docs/spec.html", by_path)
        self.assertTrue(by_path["docs/spec.html"].exists)
        self.assertIn("docs/missing.md", by_path)
        self.assertFalse(by_path["docs/missing.md"].exists)
        self.assertTrue(all(c.kind == "code" for c in claims))

    def test_pre_block_excluded(self) -> None:
        # The path inside <pre><code> is an illustrative example, not a claim.
        html = (
            "<p>claim <code>docs/missing.md</code></p>"
            "<pre><code>example <code>docs/also-missing.md</code></code></pre>"
        )
        claims, _ = self._extract(html)
        paths = {c.path for c in claims}
        self.assertIn("docs/missing.md", paths)
        self.assertNotIn("docs/also-missing.md", paths)

    def test_unclosed_pre_does_not_suppress_later_claim(self) -> None:
        # Malformed: <pre> never closes. Positional suppression keys off CLOSED ranges,
        # so a real inline claim AFTER the unclosed <pre> must still be extracted (codex
        # impl-review SHOULD-FIX — a running depth counter would silently drop it).
        html = "<pre><code>example</code><code>docs/real.md</code>"
        claims, _ = self._extract(html)
        self.assertIn("docs/real.md", {c.path for c in claims})

    def test_stray_close_pre_ignored(self) -> None:
        html = "</pre><code>docs/real.md</code>"
        claims, _ = self._extract(html)
        self.assertIn("docs/real.md", {c.path for c in claims})

    def test_href_link_repo_root(self) -> None:
        html = '<a href="/docs/spec.html">ok</a> <a href="/docs/gone.html">bad</a>'
        claims, _ = self._extract(html)
        by_path = {c.path: c for c in claims}
        self.assertTrue(by_path["docs/spec.html"].exists)
        self.assertFalse(by_path["docs/gone.html"].exists)
        self.assertTrue(all(c.kind == "link" for c in claims))

    def test_globs_braces_commands_excluded(self) -> None:
        html = (
            "<code>.codas/wiki/**</code> <code>docs/{a,b}.md</code> "
            "<code>codas check .</code> <code>plain words</code>"
        )
        claims, _ = self._extract(html)
        self.assertEqual(claims, [])

    def test_deterministic(self) -> None:
        html = "<code>docs/x.md</code> <code>docs/y.md</code>"
        a, _ = self._extract(html)
        b, _ = self._extract(html)
        self.assertEqual([(c.path, c.line, c.kind) for c in a],
                         [(c.path, c.line, c.kind) for c in b])

    def test_charref_decoded(self) -> None:
        # &lt;id&gt; decodes to <id> (no slash/ext) -> not a path claim, no crash.
        html = "<code>codas explain --finding &lt;id&gt;</code> <code>docs/real.md</code>"
        claims, _ = self._extract(html, extra=("docs/real.md",))
        self.assertEqual([c.path for c in claims], ["docs/real.md"])
        self.assertTrue(claims[0].exists)


class StaleHtmlClaimPolicy(unittest.TestCase):
    def test_both_kinds_checked_existing_skipped(self) -> None:
        ctx = ScanContext(repo=Path("/x"), config=None, roots=(), files=())  # type: ignore[arg-type]
        ctx._cache["html_claims"] = (
            DocClaim("docs/a.html", 5, "docs/gone.md", "", "code", False),
            DocClaim("docs/a.html", 9, "docs/gone2.md", "", "link", False),
            DocClaim("docs/a.html", 12, "docs/here.md", "", "code", True),
        )
        findings = check_stale_html_claim(ctx)
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(f.check_id == "stale-html-claim" for f in findings))
        self.assertTrue(all(f.severity == "warning" for f in findings))
        self.assertEqual(
            [f.evidence[0].detail for f in findings], ["docs/gone.md", "docs/gone2.md"]
        )

    def test_clean_when_all_exist(self) -> None:
        ctx = ScanContext(repo=Path("/x"), config=None, roots=(), files=())  # type: ignore[arg-type]
        ctx._cache["html_claims"] = (
            DocClaim("docs/a.html", 1, "docs/here.md", "", "code", True),
        )
        self.assertEqual(check_stale_html_claim(ctx), [])

    def test_end_to_end_fires_on_broken_authoritative_html(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".codas").mkdir()
            (repo / ".codas" / "config.yml").write_text(
                "version: 1\nconstraint_sources:\n  authoritative:\n    - docs/spec.html\n"
            )
            (repo / "docs").mkdir()
            (repo / "docs" / "spec.html").write_text(
                "<p>see <code>docs/missing-file.md</code></p>"
            )
            config = load_codas_config(repo / ".codas" / "config.yml")
            ctx = ScanContext(repo=repo, config=config, roots=("",), files=("docs/spec.html",))
            findings = check_stale_html_claim(ctx)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].check_id, "stale-html-claim")
            self.assertEqual(findings[0].evidence[0].detail, "docs/missing-file.md")

    def test_ungoverned_html_not_scanned(self) -> None:
        # An .html NOT declared in config produces no claims -> no findings.
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".codas").mkdir()
            (repo / ".codas" / "config.yml").write_text("version: 1\n")  # no constraint sources
            (repo / "notes.html").write_text("<code>docs/missing.md</code>")
            config = load_codas_config(repo / ".codas" / "config.yml")
            ctx = ScanContext(repo=repo, config=config, roots=("",), files=("notes.html",))
            self.assertEqual(check_stale_html_claim(ctx), [])


class RepoLevel(unittest.TestCase):
    def test_repo_check_has_no_stale_html_claim(self) -> None:
        from codas.app.check import run_check

        report = run_check(REPO)
        self.assertNotIn("stale-html-claim", [f.check_id for f in report.findings])

    def test_inventory_has_html_claims_block(self) -> None:
        from codas.app.inventory import run_inventory

        inventory = run_inventory(REPO)
        self.assertIn("html_claims", inventory)
        self.assertIn("references", inventory["html_claims"])
        # The 3 authoritative HTML docs are governed -> some path claims extracted.
        self.assertTrue(inventory["html_claims"]["sources"])


if __name__ == "__main__":
    unittest.main()
