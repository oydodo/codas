"""codas doctor: read-only installation diagnostics."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.app.doctor import doctor_has_failures, run_doctor

# Copy the repo's known-valid .codas/*.yml into fixtures (decouples the tests from the
# loaders' full schemas; the loaders only parse, they don't check on-disk paths).
_REPO = Path(__file__).resolve().parent.parent


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# A minimal config (vs the repo's) that declares as authoritative ONLY the .codas files
# a fixture actually contains — so doctor's config-aware optional check has a known set.
_MINIMAL_CONFIG = """\
version: 1
constraint_sources:
  authoritative:
    - .codas/config.yml
    - .codas/policies.yml
    - .codas/structure.yml
    - .codas/waivers.yml
workflow:
  adapter: trellis
  root: .trellis
dogfooding:
  protocol: docs/codas-design.html#dogfooding-protocol
"""


def _valid_repo(tmp: Path, *, program: bool = True, documents: bool = True) -> Path:
    (tmp / ".codas").mkdir(parents=True, exist_ok=True)
    for name in ("config.yml", "policies.yml", "waivers.yml", "structure.yml"):
        shutil.copy(_REPO / ".codas" / name, tmp / ".codas" / name)
    if program:
        shutil.copy(_REPO / ".codas" / "program.yml", tmp / ".codas" / "program.yml")
    if documents:
        shutil.copy(_REPO / ".codas" / "documents.yml", tmp / ".codas" / "documents.yml")
    (tmp / ".trellis" / "tasks").mkdir(parents=True, exist_ok=True)
    _write(tmp / ".trellis" / "config.yaml", "version: 1\n")
    return tmp


def _minimal_repo(tmp: Path) -> Path:
    """A valid repo whose config declares only the files present (no program/documents),
    so an absent program.yml is genuinely optional, not a declared-missing fail."""
    _valid_repo(tmp, program=False, documents=False)
    _write(tmp / ".codas" / "config.yml", _MINIMAL_CONFIG)
    return tmp


def _status(diagnostics, name: str) -> str:
    return next(d.status for d in diagnostics if d.name == name)


class DoctorTests(unittest.TestCase):
    def test_this_repo_has_no_failures(self) -> None:
        diagnostics = run_doctor(_REPO)  # repo-pinned, not caller cwd
        self.assertFalse(doctor_has_failures(diagnostics), [d for d in diagnostics if d.status == "fail"])

    def test_valid_fixture_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = run_doctor(_valid_repo(Path(tmp)))
            fails = [d.name for d in diagnostics if d.status == "fail"]
            self.assertEqual(fails, [], fails)

    def test_missing_config_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = run_doctor(Path(tmp))  # empty repo
            self.assertEqual(_status(diagnostics, "config"), "fail")
            self.assertTrue(doctor_has_failures(diagnostics))

    def test_broken_yaml_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp))
            _write(repo / ".codas" / "config.yml", "version: 1\n  bad: indent\n")
            self.assertEqual(_status(run_doctor(repo), "config"), "fail")

    def test_declared_program_missing_fails(self) -> None:
        # The repo config declares .codas/program.yml authoritative, so its absence is
        # check-failing (config_sources error) -> doctor must fail, not warn.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp), program=False)
            diagnostics = run_doctor(repo)
            self.assertEqual(_status(diagnostics, "program_plan"), "fail")
            self.assertTrue(doctor_has_failures(diagnostics))

    def test_undeclared_program_absent_warns_not_fails(self) -> None:
        # When config does NOT declare program.yml, its absence is genuinely optional.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _minimal_repo(Path(tmp))
            diagnostics = run_doctor(repo)
            self.assertEqual(_status(diagnostics, "program_plan"), "warn")
            self.assertFalse(doctor_has_failures(diagnostics), [d for d in diagnostics if d.status == "fail"])

    def test_legacy_prototype_leftover_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp))
            _write(repo / "src" / "harness_guard" / "__init__.py", "")
            diagnostics = run_doctor(repo)
            self.assertEqual(_status(diagnostics, "legacy_prototype"), "fail")
            self.assertTrue(doctor_has_failures(diagnostics))

    def test_trellis_tasks_root_missing_fails(self) -> None:
        # A present .trellis/ without tasks/ still fails check_trellis_context.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp))
            shutil.rmtree(repo / ".trellis" / "tasks")
            self.assertEqual(_status(run_doctor(repo), "trellis_context"), "fail")

    def test_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp))
            names1 = [d.name for d in run_doctor(repo)]
            names2 = [d.name for d in run_doctor(repo)]
            self.assertEqual(names1, names2)
            self.assertEqual(names1[0], "git_repo")


class GateVisibilityTests(unittest.TestCase):
    """gaps 1/4: doctor SEES the git hooks + Claude SessionStart hook + AGENTS/CLAUDE freshness.
    All WARN-only — visibility, not a gate (a fresh clone with no hooks must not fail doctor)."""

    def _diag(self, diagnostics, name: str):
        return next(d for d in diagnostics if d.name == name)

    def test_absent_hooks_and_docs_warn_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp))  # .codas + .trellis, but no hooks / .claude / AGENTS
            diagnostics = run_doctor(repo)
            for name in ("git_hooks", "agent_hook", "agents_block", "claude_shim"):
                self.assertEqual(self._diag(diagnostics, name).status, "warn", name)
            self.assertFalse(doctor_has_failures(diagnostics))  # visibility, never a gate

    def test_installed_hooks_and_docs_report_ok(self) -> None:
        from codas.app.agent_docs import write_agent_docs
        from codas.app.hooks import install_agent_injection, install_git_hooks

        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(Path(tmp))
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            install_git_hooks(repo, command="echo check")
            write_agent_docs(repo)
            install_agent_injection(repo, command="echo preflight")
            diagnostics = run_doctor(repo)
            for name in ("git_hooks", "agent_hook", "agents_block", "claude_shim"):
                self.assertEqual(self._diag(diagnostics, name).status, "ok", name)
            # SessionStart trust cannot be probed -> the OK detail advises approving it
            self.assertIn("workspace-trust", self._diag(diagnostics, "agent_hook").detail)

    def test_status_helpers_on_bare_dir(self) -> None:
        from codas.integrations.claude import session_hook_status
        from codas.integrations.enforcement import git_hook_status

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(session_hook_status(repo), "absent")
            self.assertEqual(set(git_hook_status(repo).values()), {"absent"})


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
