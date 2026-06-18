from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.structure.program_loader import ProgramPlanError, load_program_plan

VALID_PLAN = """\
version: 1
kind: program_plan
defaults:
  status: planned
work_items:
  - id: program:P0:cli-core
    phase: P0
    title: CLI core
    status: completed
    depends_on: []
  - id: program:P1:foundation
    phase: P1
    title: Foundation
    status: in_progress
    depends_on:
      - program:P0:cli-core
    trellis_tasks:
      - 06-18-foundation
    exit_criteria:
      - it works
"""


def _load(text: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "program.yml"
        path.write_text(text)
        return load_program_plan(path, source="program.yml")


class ProgramLoaderTests(unittest.TestCase):
    def test_valid_plan_loads(self) -> None:
        plan = _load(VALID_PLAN)
        self.assertEqual(len(plan.work_items), 2)
        self.assertEqual(plan.work_items[1].depends_on, ("program:P0:cli-core",))
        self.assertEqual(plan.work_items[1].exit_criteria, ("it works",))

    def test_real_repo_plan_loads(self) -> None:
        plan = load_program_plan(
            Path.cwd() / ".codas" / "program.yml", source=".codas/program.yml"
        )
        self.assertEqual(len(plan.work_items), 8)

    def test_invalid_id_raises(self) -> None:
        broken = VALID_PLAN.replace("program:P0:cli-core", "P0-cli-core")
        with self.assertRaises(ProgramPlanError):
            _load(broken)

    def test_dangling_dependency_raises(self) -> None:
        broken = VALID_PLAN.replace("      - program:P0:cli-core", "      - program:P9:ghost")
        with self.assertRaises(ProgramPlanError):
            _load(broken)

    def test_cycle_raises(self) -> None:
        cyclic = """\
version: 1
kind: program_plan
work_items:
  - id: program:P0:a
    phase: P0
    title: A
    status: planned
    depends_on:
      - program:P1:b
  - id: program:P1:b
    phase: P1
    title: B
    status: planned
    depends_on:
      - program:P0:a
"""
        with self.assertRaises(ProgramPlanError):
            _load(cyclic)


if __name__ == "__main__":
    unittest.main()
