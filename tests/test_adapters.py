from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.adapters.markdown import extract_doc_claims
from codas.adapters.trellis import extract_task_facts
from codas.config.loader import CodasConfig


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class MarkdownAdapterTests(unittest.TestCase):
    def _claims(self, repo: Path):
        files = tuple(
            p.relative_to(repo).as_posix() for p in repo.rglob("*.md")
        )
        return extract_doc_claims(repo, files)

    def test_link_and_backtick_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "docs" / "real.md", "x")
            _write(
                repo / "README.md",
                "See [doc](docs/real.md) and `src/codas/cli.py` and `docs/missing.html`.\n",
            )
            claims = {(c.path, c.exists) for c in self._claims(repo)}
            self.assertIn(("docs/real.md", True), claims)
            self.assertIn(("docs/missing.html", False), claims)

    def test_relative_link_resolved_against_source_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "wiki" / "concepts" / "a.md", "x")
            _write(repo / "wiki" / "index.md", "[a](concepts/a.md) and [b](./b.md)\n")
            claims = {c.path: c.exists for c in self._claims(repo)}
            self.assertTrue(claims.get("wiki/concepts/a.md"))
            self.assertIn("wiki/b.md", claims)  # resolved, missing

    def test_titled_link_strips_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "README.md", '[x](docs/a.md "the title")\n')
            paths = {c.path for c in self._claims(repo)}
            self.assertIn("docs/a.md", paths)

    def test_image_and_external_and_anchor_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / "README.md",
                "![img](assets/logo.png)\n[ext](https://x.com/a.md)\n[anc](#section)\n",
            )
            self.assertEqual(self._claims(repo), [])

    def test_fenced_code_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / "README.md",
                "```\n`src/codas/cli.py`\n[x](docs/a.md)\n```\nplain `docs/b.md`\n",
            )
            paths = {c.path for c in self._claims(repo)}
            self.assertNotIn("src/codas/cli.py", paths)
            self.assertNotIn("docs/a.md", paths)
            self.assertIn("docs/b.md", paths)

    def test_fragment_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "docs" / "d.html", "x")
            _write(repo / "README.md", "`docs/d.html#anchor`\n")
            claim = next(c for c in self._claims(repo) if c.path == "docs/d.html")
            self.assertEqual(claim.fragment, "anchor")
            self.assertTrue(claim.exists)

    def test_prose_word_and_reference_style_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "README.md", "use `useMemo` here\n[t][id]\n[id]: docs/x.md\n")
            paths = {c.path for c in self._claims(repo)}
            self.assertNotIn("useMemo", paths)
            self.assertNotIn("docs/x.md", paths)  # reference-style not resolved

    def test_task_dirs_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".trellis" / "tasks" / "t" / "prd.md", "`docs/x.md`\n")
            files = (".trellis/tasks/t/prd.md",)
            self.assertEqual(extract_doc_claims(repo, files), [])

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "README.md", "[a](docs/a.md) `src/b.py` [c](docs/c.md)\n")
            self.assertEqual(self._claims(repo), self._claims(repo))


class TrellisAdapterTests(unittest.TestCase):
    def _config(self, repo: Path) -> CodasConfig:
        return CodasConfig(path=repo / ".codas" / "config.yml", raw={}, workflow_root=".trellis")

    def test_active_and_archived_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".trellis" / "tasks" / "a" / "task.json",
                '{"id": "a", "status": "in_progress", "package": "p"}',
            )
            _write(
                repo / ".trellis" / "tasks" / "archive" / "2026-06" / "b" / "task.json",
                '{"id": "b", "status": "completed"}',
            )
            facts = extract_task_facts(repo, self._config(repo))
            by_id = {t.id: t for t in facts.items}
            self.assertFalse(by_id["a"].archived)
            self.assertTrue(by_id["b"].archived)
            self.assertIsNone(by_id["b"].package)
            self.assertEqual(facts.skipped, ())

    def test_malformed_task_json_is_skipped_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".trellis" / "tasks" / "bad" / "task.json", "{not json")
            _write(
                repo / ".trellis" / "tasks" / "ok" / "task.json",
                '{"id": "ok", "status": "planning"}',
            )
            facts = extract_task_facts(repo, self._config(repo))
            self.assertEqual([t.id for t in facts.items], ["ok"])
            self.assertEqual(facts.skipped, (".trellis/tasks/bad/task.json",))


if __name__ == "__main__":
    unittest.main()
