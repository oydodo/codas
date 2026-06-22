"""P6 enforcement gates: git hook installer + GitHub Action render."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.app.hooks import install_git_hooks
from codas.integrations.enforcement import (
    HOOK_MARKER,
    HOOK_NAMES,
    render_hook,
    render_workflow,
)

_REPO = Path(__file__).resolve().parent.parent


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)


class RenderTests(unittest.TestCase):
    def test_render_hook_is_deterministic_and_marked(self) -> None:
        body = render_hook("pre-commit")
        self.assertEqual(body, render_hook("pre-commit"))
        self.assertTrue(body.startswith("#!/bin/sh\n"))
        self.assertIn(HOOK_MARKER, body)
        self.assertIn("codas check .", body)

    def test_render_hook_custom_command(self) -> None:
        self.assertIn("PYTHONPATH=src python -m codas check .", render_hook("pre-push", "PYTHONPATH=src python -m codas check ."))

    def test_render_workflow_is_deterministic(self) -> None:
        self.assertEqual(render_workflow(), render_workflow())
        self.assertIn("codas check", render_workflow())
        # The freshness verifies are the binding staleness gate (doctor only warns).
        self.assertIn("codas agents --verify", render_workflow())
        self.assertIn("codas wiki --verify", render_workflow())

    def test_committed_workflow_matches_render(self) -> None:
        # The committed CI gate must equal render_workflow() byte-for-byte, so editing
        # the renderer without regenerating the file is caught.
        committed = (_REPO / ".github" / "workflows" / "codas.yml").read_text()
        self.assertEqual(committed, render_workflow())


class InstallHooksTests(unittest.TestCase):
    def test_install_writes_executable_marked_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            result = install_git_hooks(repo)
            self.assertIsNotNone(result)
            self.assertEqual(set(result.installed), set(HOOK_NAMES))
            for name in HOOK_NAMES:
                path = repo / ".git" / "hooks" / name
                self.assertTrue(path.exists())
                self.assertTrue(os.access(path, os.X_OK), f"{name} not executable")
                self.assertIn(HOOK_MARKER, path.read_text())

    def test_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            install_git_hooks(repo)
            first = (repo / ".git" / "hooks" / "pre-commit").read_text()
            result = install_git_hooks(repo)  # re-run on its own marked hooks
            self.assertEqual(set(result.installed), set(HOOK_NAMES))
            self.assertEqual(result.skipped, ())
            self.assertEqual(first, (repo / ".git" / "hooks" / "pre-commit").read_text())

    def test_foreign_hook_skipped_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            foreign = repo / ".git" / "hooks" / "pre-commit"
            foreign.write_text("#!/bin/sh\necho mine\n")
            result = install_git_hooks(repo)
            self.assertIn("pre-commit", result.skipped)
            self.assertIn("pre-push", result.installed)
            self.assertEqual(foreign.read_text(), "#!/bin/sh\necho mine\n")

    def test_force_overwrites_foreign_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            (repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\necho mine\n")
            result = install_git_hooks(repo, force=True)
            self.assertEqual(set(result.installed), set(HOOK_NAMES))
            self.assertIn(HOOK_MARKER, (repo / ".git" / "hooks" / "pre-commit").read_text())

    def test_non_git_repo_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(install_git_hooks(Path(tmp)))

    def test_command_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            install_git_hooks(repo, command="PYTHONPATH=src python3 -m codas check .")
            body = (repo / ".git" / "hooks" / "pre-commit").read_text()
            # No `exec` — `exec VAR=val cmd` is invalid in sh; the command runs as the last
            # line and the hook exits with its status (env-prefixed commands must work).
            self.assertIn("\nPYTHONPATH=src python3 -m codas check .\n", body)
            self.assertNotIn("exec ", body)

    def test_marker_substring_in_foreign_hook_not_clobbered(self) -> None:
        # The marker on a non-line-2 comment must NOT mark the hook as Codas-owned.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            foreign = repo / ".git" / "hooks" / "pre-commit"
            foreign.write_text(f"#!/bin/sh\necho mine\n{HOOK_MARKER} mentioned in passing\n")
            result = install_git_hooks(repo)
            self.assertIn("pre-commit", result.skipped)
            self.assertIn("echo mine", foreign.read_text())

    def test_file_valued_hookspath_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            (repo / "a_file").write_text("not a dir\n")
            subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", "a_file"], check=True)
            self.assertIsNone(install_git_hooks(repo))

    def test_relative_hookspath_resolved_from_worktree_root(self) -> None:
        # Invoked from a subdir, a relative core.hooksPath must resolve to the worktree
        # root (where Git runs it), not the subdir.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git_init(repo)
            subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".githooks"], check=True)
            subdir = repo / "src" / "deep"
            subdir.mkdir(parents=True)
            result = install_git_hooks(subdir)
            self.assertIsNotNone(result)
            self.assertTrue((repo / ".githooks" / "pre-commit").exists())
            self.assertFalse((subdir / ".githooks").exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
