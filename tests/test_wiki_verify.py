from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from codas.app.wiki import verify_generated_sections, write_generated_sections
from codas.cli import main
from codas.config.loader import load_codas_config

CONFIG = """\
version: 1
constraint_sources:
  authoritative: []
  supporting: []
workspace:
  roots:
    - .
wiki:
  path: .codas/wiki
"""

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


def _mini_repo(directory: str) -> Path:
    repo = Path(directory)
    (repo / ".codas").mkdir(parents=True, exist_ok=True)
    (repo / ".codas" / "config.yml").write_text(CONFIG)
    (repo / ".codas" / "structure.yml").write_text(STRUCTURE)
    (repo / ".codas" / "program.yml").write_text(PROGRAM)
    return repo


class VerifyGeneratedSectionsTests(unittest.TestCase):
    def test_fresh_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = _mini_repo(directory)
            write_generated_sections(repo)
            self.assertEqual(verify_generated_sections(repo), [])

    def test_hand_edit_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = _mini_repo(directory)
            [page] = write_generated_sections(repo)
            page.write_text(page.read_text() + "\nhand edit\n")
            self.assertEqual(verify_generated_sections(repo), [page])

    def test_missing_page_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = _mini_repo(directory)
            stale = verify_generated_sections(repo)  # never written
            self.assertEqual(len(stale), 1)


class WikiVerifyCliTests(unittest.TestCase):
    def test_verify_clean_real_repo(self) -> None:
        # The committed governance.md was regenerated in this slice -> fresh.
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["wiki", str(Path.cwd()), "--verify"])
        self.assertEqual(code, 0)
        self.assertIn("up to date", buffer.getvalue())

    def test_verify_stale_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = _mini_repo(directory)
            [page] = write_generated_sections(repo)
            page.write_text("hand edit")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["wiki", str(repo), "--verify"])
            self.assertEqual(code, 1)
            self.assertIn("stale", buffer.getvalue())

    def test_verify_write_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["wiki", str(Path.cwd()), "--verify", "--write"])
        self.assertEqual(caught.exception.code, 2)


class ContractRegistrationTests(unittest.TestCase):
    def test_contract_exists_and_declared_supporting(self) -> None:
        repo = Path.cwd()
        self.assertTrue((repo / "CONTRACT.md").exists())
        config = load_codas_config(repo / ".codas" / "config.yml")
        self.assertIn("CONTRACT.md", config.supporting_sources)


if __name__ == "__main__":
    unittest.main()
