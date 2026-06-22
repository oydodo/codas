"""Codex agent integration: the .codex/hooks.json installer, the registry seam, the doctor
probe (opt-in), the no-shim contract, and the byte-identical exclusion of the per-machine
hook file.

Covers the codex-review-folded design: UserPromptSubmit-primary per-turn carrier,
agent-neutral envelope reuse, and the install-state per-agent namespace."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.app.doctor import run_doctor
from codas.app.hooks import install_agent_injection
from codas.integrations.codex import (
    codex_turn_specs,
    install_codex_session_hook,
    install_codex_turn_hooks,
)
from codas.integrations.install_state import read_install_state
from codas.integrations.registry import AGENTS, select_agents
from codas.structure.index import _walk_files


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _hooks_json(repo: Path) -> dict:
    return json.loads((repo / ".codex" / "hooks.json").read_text())


def _valid_repo(tmp: str) -> Path:
    repo = Path(tmp)
    _write(repo / ".codas" / "config.yml", "version: 1\n")
    return repo


class RegistryTests(unittest.TestCase):
    def test_registry_has_both_agents(self) -> None:
        self.assertEqual(set(AGENTS), {"claude", "codex"})
        self.assertTrue(AGENTS["claude"].has_shim)
        self.assertFalse(AGENTS["codex"].has_shim)

    def test_select_agents(self) -> None:
        self.assertEqual([i.name for i in select_agents("claude")], ["claude"])
        self.assertEqual([i.name for i in select_agents("codex")], ["codex"])
        self.assertEqual([i.name for i in select_agents("all")], ["claude", "codex"])
        self.assertEqual(select_agents("nope"), ())


class CodexInstallTests(unittest.TestCase):
    def test_install_writes_valid_hooks_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            install_codex_session_hook(repo, command="run preflight")
            install_codex_turn_hooks(repo, runner="HOOK")
            data = _hooks_json(repo)
            self.assertIn("SessionStart", data["hooks"])
            # The codex per-turn carriers: UserPromptSubmit (primary) + PostToolUse (edit).
            self.assertIn("UserPromptSubmit", data["hooks"])
            self.assertIn("PostToolUse", data["hooks"])
            # Stop/SubagentStop deliberately omitted (unproven on Codex).
            self.assertNotIn("Stop", data["hooks"])
            self.assertNotIn("SubagentStop", data["hooks"])
            matchers = [g.get("matcher") for g in data["hooks"]["PostToolUse"]]
            self.assertIn("apply_patch|Edit|Write", matchers)

    def test_idempotent_and_foreign_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            # A foreign UserPromptSubmit group must survive our install.
            _write(
                repo / ".codex" / "hooks.json",
                json.dumps(
                    {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "mine"}]}]}}
                ),
            )
            install_codex_turn_hooks(repo, runner="HOOK")
            once = (repo / ".codex" / "hooks.json").read_bytes()
            install_codex_turn_hooks(repo, runner="HOOK")
            self.assertEqual((repo / ".codex" / "hooks.json").read_bytes(), once)
            groups = _hooks_json(repo)["hooks"]["UserPromptSubmit"]
            commands = [h["command"] for g in groups for h in g["hooks"]]
            self.assertTrue(any(c == "mine" for c in commands))  # foreign preserved
            self.assertTrue(any("HOOK UserPromptSubmit" in c for c in commands))  # ours added

    def test_install_agent_injection_codex_records_state_and_no_shim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(tmp)
            result = install_agent_injection(repo, command="run preflight", agents="codex")
            state = read_install_state(repo)
            self.assertIn("codex", state["agent_hooks"])
            self.assertNotIn("claude", state["agent_hooks"])  # codex-only never touches claude
            for spec in codex_turn_specs():
                self.assertIn(spec.key, state["agent_hooks"]["codex"])
            self.assertEqual([i.name for i in result.installs], ["codex"])
            # Codex reads AGENTS.md natively — no CLAUDE.md shim is written.
            self.assertFalse((repo / "CLAUDE.md").is_file())

    def test_all_agents_install_both_and_merge_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(tmp)
            install_agent_injection(repo, command="run preflight", agents="all")
            state = read_install_state(repo)
            self.assertEqual(set(state["agent_hooks"]), {"claude", "codex"})

    def test_installing_codex_preserves_existing_claude_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(tmp)
            install_agent_injection(repo, command="run preflight", agents="claude")
            install_agent_injection(repo, command="run preflight", agents="codex")
            state = read_install_state(repo)
            self.assertEqual(set(state["agent_hooks"]), {"claude", "codex"})


class CodexByteIdenticalTests(unittest.TestCase):
    def test_codex_hooks_json_excluded_from_walk_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "src" / "a.py", "x = 1\n")
            _write(repo / ".codex" / "hooks.json", '{"hooks": {}}\n')
            walked = _walk_files(repo)
            self.assertNotIn(".codex/hooks.json", walked)
            self.assertIn("src/a.py", walked)


class CodexDoctorTests(unittest.TestCase):
    def _diag(self, diagnostics, name: str):
        return next((d for d in diagnostics if d.name == name), None)

    def test_codex_not_probed_when_not_opted_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(tmp)
            diagnostics = run_doctor(repo)
            # No codex diagnostics for a claude-only/default repo (no noise).
            self.assertIsNone(self._diag(diagnostics, "codex_hook"))
            self.assertIsNone(self._diag(diagnostics, "codex_turn_hooks"))

    def test_codex_probed_after_install_with_trust_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _valid_repo(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            install_agent_injection(repo, command="echo preflight", agents="codex")
            diagnostics = run_doctor(repo)
            session = self._diag(diagnostics, "codex_hook")
            turn = self._diag(diagnostics, "codex_turn_hooks")
            self.assertIsNotNone(session)
            self.assertIsNotNone(turn)
            self.assertIn("trust", session.detail.lower())
            # Codex has 2 per-turn groups (UserPromptSubmit + PostToolUse).
            self.assertIn("/2", turn.detail)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
