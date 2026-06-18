from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.policies.trellis_context import check_trellis_context


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _config(repo: Path, task_globs: tuple[str, ...] = ()) -> CodasConfig:
    return CodasConfig(
        path=repo / ".codas" / "config.yml",
        raw={},
        workflow_adapter="trellis",
        workflow_root=".trellis",
        workflow_task_globs=task_globs,
    )


class TrellisContextRealignTests(unittest.TestCase):
    def _ids(self, findings):
        return {f.check_id for f in findings}

    def test_prd_only_task_has_no_context_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            task = repo / ".trellis" / "tasks" / "t"
            _write(task / "task.json", "{}")
            _write(task / "prd.md", "# PRD")
            findings = check_trellis_context(repo, _config(repo))
            self.assertNotIn("trellis-task-context-missing", self._ids(findings))

    def test_missing_jsonl_no_longer_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            task = repo / ".trellis" / "tasks" / "t"
            _write(task / "task.json", "{}")
            _write(task / "prd.md", "# PRD")
            # no implement.jsonl / check.jsonl
            findings = check_trellis_context(repo, _config(repo))
            missing = [
                f for f in findings if f.check_id == "trellis-task-context-missing"
            ]
            self.assertEqual(missing, [])

    def test_missing_prd_still_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            task = repo / ".trellis" / "tasks" / "t"
            _write(task / "task.json", "{}")
            findings = check_trellis_context(repo, _config(repo))
            warned = [
                f
                for f in findings
                if f.check_id == "trellis-task-context-missing"
                and f.meta.get("missing_file") == "prd.md"
            ]
            self.assertEqual(len(warned), 1)

    def test_glob_check_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".trellis" / "tasks" / "t" / "task.json", "{}")
            _write(repo / ".trellis" / "tasks" / "t" / "prd.md", "# PRD")
            # config with NO implement/check.jsonl globs
            findings = check_trellis_context(repo, _config(repo, task_globs=()))
            self.assertNotIn("trellis-task-glob-missing", self._ids(findings))


if __name__ == "__main__":
    unittest.main()
