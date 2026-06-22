"""Per-turn injection hook shim (gap 3, step 3/4): the Claude turn-hook installer, the
envelope entrypoint, and the per-group status probe.

Covers S6 (generalized (event, matcher) groups + foreign-preservation + idempotence) and the
envelope contract verified for Stop/SubagentStop/PostToolUse."""
from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from codas.app.hooks import install_agent_injection
from codas.integrations.claude import (
    claude_hook_status,
    install_claude_session_hook,
    install_claude_turn_hooks,
    turn_hook_specs,
)
from codas.integrations.agent_hook import run_agent_hook
from codas.integrations.install_state import read_install_state


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _settings(repo: Path) -> dict:
    return json.loads((repo / ".claude" / "settings.json").read_text())


_MAP_ROOT = (
    "version: 1\nkind: structure_map\nunits:\n"
    "  root:\n    path: .\n    kind: repository\n    owner: C\n"
    "    purpose: x\n    canonical_placement: x\n"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class TurnHookInstallTests(unittest.TestCase):
    def test_fresh_install_creates_all_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            results = install_claude_turn_hooks(repo, runner="HOOK")
            self.assertEqual(
                set(results), {s.key for s in turn_hook_specs()}
            )
            hooks = _settings(repo)["hooks"]
            self.assertEqual(len(hooks["Stop"]), 1)
            self.assertEqual(len(hooks["SubagentStop"]), 1)
            # 3 matcher-keyed PostToolUse groups (Task/Agent, mcp-codex, Edit family).
            matchers = {g["matcher"] for g in hooks["PostToolUse"]}
            self.assertEqual(matchers, {"Task|Agent", "mcp__.*codex.*", "Edit|Write|MultiEdit"})
            self.assertIn("codas-managed-hook", hooks["Stop"][0]["hooks"][0]["command"])
            self.assertIn("HOOK Stop", hooks["Stop"][0]["hooks"][0]["command"])

    def test_idempotent_no_byte_churn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            install_claude_turn_hooks(repo, runner="HOOK")
            once = (repo / ".claude" / "settings.json").read_bytes()
            install_claude_turn_hooks(repo, runner="HOOK")
            self.assertEqual((repo / ".claude" / "settings.json").read_bytes(), once)

    def test_reinstall_reports_installed_not_refreshed(self) -> None:
        # A byte-identical re-install must report `installed`, not `refreshed` (S4).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            install_claude_turn_hooks(repo, runner="HOOK")
            again = install_claude_turn_hooks(repo, runner="HOOK")
            self.assertTrue(all(r.status == "installed" for r in again.values()), again)

    def test_foreign_posttooluse_group_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(
                repo / ".claude" / "settings.json",
                json.dumps(
                    {"hooks": {"PostToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine"}]}
                    ]}}
                ),
            )
            install_claude_turn_hooks(repo, runner="HOOK")
            groups = _settings(repo)["hooks"]["PostToolUse"]
            commands = [g["hooks"][0]["command"] for g in groups]
            self.assertIn("mine", commands)  # foreign Bash matcher untouched
            self.assertEqual(sum("codas-managed-hook" in c for c in commands), 3)

    def test_malformed_settings_not_clobbered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / ".claude" / "settings.json", "{not json")
            results = install_claude_turn_hooks(repo, runner="HOOK")
            self.assertEqual(results["_"].status, "malformed")
            self.assertEqual(
                (repo / ".claude" / "settings.json").read_text(), "{not json"
            )

    def test_session_group_carries_baseline_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            install_claude_session_hook(repo, command="run preflight")
            commands = [
                h["command"] for h in _settings(repo)["hooks"]["SessionStart"][0]["hooks"]
            ]
            self.assertTrue(any("run preflight" in c for c in commands))
            self.assertTrue(any("status --record-baseline" in c for c in commands))

    def test_session_and_turn_installs_coexist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            install_claude_session_hook(repo, command="run preflight")
            install_claude_turn_hooks(repo, runner="HOOK")  # must preserve SessionStart
            hooks = _settings(repo)["hooks"]
            self.assertIn("SessionStart", hooks)
            self.assertIn("Stop", hooks)
            self.assertIn("run preflight", hooks["SessionStart"][0]["hooks"][0]["command"])


class HookStatusProbeTests(unittest.TestCase):
    def test_probe_installed_and_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(claude_hook_status(repo, "Stop", None), "absent")
            install_claude_turn_hooks(repo, runner="HOOK")
            self.assertEqual(claude_hook_status(repo, "Stop", None), "installed")
            self.assertEqual(
                claude_hook_status(repo, "PostToolUse", "mcp__.*codex.*"), "installed"
            )
            # A matcher we never install is not ours.
            self.assertEqual(claude_hook_status(repo, "PostToolUse", "Bash"), "absent")

    def test_probe_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / ".claude" / "settings.json", "{bad")
            self.assertEqual(claude_hook_status(repo, "Stop", None), "malformed")


class EnvelopeEntrypointTests(unittest.TestCase):
    def _fire(self, repo: Path, event: str) -> str:
        stdin = io.StringIO(json.dumps({"cwd": str(repo)}))
        stdin.isatty = lambda: False  # type: ignore[method-assign]
        out = io.StringIO()
        with mock.patch("sys.stdin", stdin), redirect_stdout(out):
            rc = run_agent_hook([event])
        self.assertEqual(rc, 0)
        return out.getvalue()

    def _repo(self, tmp: str) -> Path:
        repo = Path(tmp)
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
        _write(repo / ".codas" / "config.yml", "version: 1\n")
        _write(repo / ".codas" / "structure.yml", _MAP_ROOT)
        _write(repo / "src" / "a.py", "def handle():\n    pass\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
        return repo

    def test_emits_envelope_echoing_each_injecting_event(self) -> None:
        for event in ("Stop", "SubagentStop", "PostToolUse"):
            with tempfile.TemporaryDirectory() as tmp:
                repo = self._repo(tmp)
                _write(repo / "src" / "b.py", "def handle():\n    pass\n")  # collision

                payload = json.loads(self._fire(repo, event))

                # hookEventName MUST echo the firing event (Claude validates it).
                self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], event)
                self.assertIn(
                    "also defined in src/a.py",
                    payload["hookSpecificOutput"]["additionalContext"],
                )

    def test_non_injecting_event_emits_nothing_even_with_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")  # collision present
            # An event outside _INJECTING_EVENTS (e.g. a stray arg) must inject nothing.
            self.assertEqual(self._fire(repo, "SessionStart"), "")

    def test_clean_turn_emits_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)  # committed, clean
            self.assertEqual(self._fire(repo, "Stop"), "")

    def test_never_raises_on_broken_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)  # no .codas
            self.assertEqual(self._fire(repo, "Stop"), "")


class InstallStateTests(unittest.TestCase):
    def test_install_agent_injection_records_turn_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / ".codas" / "config.yml", "version: 1\n")
            install_agent_injection(repo, command="run preflight")
            claude = read_install_state(repo)["agent_hooks"]["claude"]
            for key in (s.key for s in turn_hook_specs()):
                self.assertIn(key, claude)
                self.assertEqual(claude[key]["status"], "installed")


if __name__ == "__main__":
    unittest.main()
