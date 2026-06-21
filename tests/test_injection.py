from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codas.adapters.markdown import extract_doc_claims
from codas.app.agents_block import (
    BLOCK_END,
    BLOCK_START,
    _enforcement,
    agents_pages,
    render_codas_block,
    splice_managed_block,
    verify_agents_block,
    write_agents_block,
)
from codas.app.hooks import install_agent_injection
from codas.app.preflight import build_context_pack
from codas.config.loader import load_policies
from codas.integrations.claude import (
    install_claude_session_hook,
    verify_claude_shim,
    write_claude_shim,
)
from codas.integrations.install_state import read_install_state
from codas.structure.index import _walk_files
from codas.structure.loader import load_structure_map


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# A structure map whose unit paths deliberately carry known extensions (.html / .yml) and
# whose canonical_placement prose names a slash+ext path — so the doc-claim-neutrality test
# (must-hold #4) actually exercises the case that would churn the hash if mishandled.
_STRUCTURE_YML = (
    "version: 1\nkind: structure_map\nunits:\n"
    "  pkg:\n    path: src/pkg\n    kind: package\n    owner: Owner\n"
    "    purpose: p\n    canonical_placement: Code belongs under src/pkg and config in .codas/config.yml.\n"
    "  schema-doc:\n    path: docs/schema.html\n    kind: schema_doc\n    owner: Architect\n"
    "    purpose: p\n    canonical_placement: The schema lives at docs/schema.html.\n"
)
_POLICIES_YML = (
    "version: 1\npolicies:\n"
    "  stale_claim:\n    severity: warning\n"
    "  structure_drift:\n    severity: error\n"
    "  duplicate_concept:\n    severity: error\n    status: planned\n"
)


class EnforcementDerivationTests(unittest.TestCase):
    def test_tag_is_a_projection_of_severity_and_status(self) -> None:
        self.assertEqual(_enforcement("error", None), "gated")
        self.assertEqual(_enforcement("warning", None), "advisory")
        self.assertEqual(_enforcement("error", "planned"), "planned")
        self.assertEqual(_enforcement("warning", "planned"), "planned")


class RenderBlockTests(unittest.TestCase):
    def _render(self, repo: Path) -> str:
        _write(repo / ".codas" / "structure.yml", _STRUCTURE_YML)
        _write(repo / ".codas" / "policies.yml", _POLICIES_YML)
        return render_codas_block(
            load_policies(repo / ".codas" / "policies.yml"),
            load_structure_map(repo / ".codas" / "structure.yml"),
        )

    def test_deterministic_and_marker_wrapped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            block = self._render(repo)
            self.assertEqual(block, self._render(repo))
            self.assertTrue(block.startswith(BLOCK_START))
            self.assertTrue(block.rstrip().endswith(BLOCK_END))
            # enforcement tags surface; the planned policy reads "planned", not "gated"
            self.assertIn("| `duplicate_concept` |", block)
            self.assertIn("planned", block)

    def test_missing_blurb_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "structure.yml", _STRUCTURE_YML)
            _write(
                repo / ".codas" / "policies.yml",
                "version: 1\npolicies:\n  made_up_policy:\n    severity: error\n",
            )
            with self.assertRaises(ValueError):
                render_codas_block(
                    load_policies(repo / ".codas" / "policies.yml"),
                    load_structure_map(repo / ".codas" / "structure.yml"),
                )

    def test_block_creates_no_doc_claims(self) -> None:
        """must-hold #4: the scanned AGENTS.md gains NO doc_claim from the rendered block, even
        though the ownership table carries extension-bearing unit paths (rendered plain, never
        in a backtick span or link). The strongest form of the test: extract over a file that
        contains ONLY the block returns nothing."""
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            block = self._render(repo)
            (repo / "AGENTS.md").write_text(block, encoding="utf-8")
            claims = extract_doc_claims(repo, ("AGENTS.md",))
            self.assertEqual(claims, [], f"block leaked doc_claims: {claims}")


class SpliceTests(unittest.TestCase):
    def test_append_when_absent_then_replace_in_place(self) -> None:
        block_a = f"{BLOCK_START}\nA\n{BLOCK_END}"
        block_b = f"{BLOCK_START}\nB\n{BLOCK_END}"
        existing = "# Hand title\n\nkeep me\n"
        once = splice_managed_block(existing, block_a)
        self.assertIn("keep me", once)
        self.assertIn(block_a, once)
        # re-splice replaces ONLY the managed region, preserving the hand content
        twice = splice_managed_block(once, block_b)
        self.assertIn("keep me", twice)
        self.assertIn(block_b, twice)
        self.assertNotIn("\nA\n", twice)

    def test_idempotent(self) -> None:
        block = f"{BLOCK_START}\nX\n{BLOCK_END}"
        once = splice_managed_block("outside\n", block)
        self.assertEqual(once, splice_managed_block(once, block))


class WriteVerifyTests(unittest.TestCase):
    def _repo(self, repo: Path) -> None:
        _write(repo / ".codas" / "structure.yml", _STRUCTURE_YML)
        _write(repo / ".codas" / "policies.yml", _POLICIES_YML)
        _write(repo / "AGENTS.md", "<!-- TRELLIS:START -->\nkeep\n<!-- TRELLIS:END -->\n")

    def test_write_then_verify_clean_and_preserves_trellis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._repo(repo)
            written = write_agents_block(repo)
            self.assertEqual(written, [repo / "AGENTS.md"])
            self.assertIn("<!-- TRELLIS:START -->", (repo / "AGENTS.md").read_text())
            self.assertEqual(verify_agents_block(repo), [])

    def test_hand_edit_inside_block_flags_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._repo(repo)
            write_agents_block(repo)
            text = (repo / "AGENTS.md").read_text()
            tampered = text.replace("# Codas governance", "# Hacked governance")
            (repo / "AGENTS.md").write_text(tampered, encoding="utf-8")
            self.assertEqual(verify_agents_block(repo), [repo / "AGENTS.md"])

    def test_edit_outside_block_does_not_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._repo(repo)
            write_agents_block(repo)
            text = (repo / "AGENTS.md").read_text()
            (repo / "AGENTS.md").write_text(text + "\nhand addendum\n", encoding="utf-8")
            self.assertEqual(verify_agents_block(repo), [])
            # the expected render carries the new outside content, so it stays verified
            self.assertIn("hand addendum", next(iter(agents_pages(repo).values())))


class ClaudeShimTests(unittest.TestCase):
    def test_shim_write_verify_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            written = write_claude_shim(repo)
            self.assertEqual(written, [repo / "CLAUDE.md"])
            text = (repo / "CLAUDE.md").read_text()
            self.assertIn("@AGENTS.md", text)
            self.assertEqual(verify_claude_shim(repo), [])
            # @AGENTS.md is plain text -> not a doc_claim
            self.assertEqual(extract_doc_claims(repo, ("CLAUDE.md",)), [])


class SessionHookTests(unittest.TestCase):
    def _settings(self, repo: Path) -> dict:
        return json.loads((repo / ".claude" / "settings.json").read_text())

    def test_fresh_install_idempotent_and_marker_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            first = install_claude_session_hook(repo, command="run preflight")
            self.assertEqual(first.status, "installed")
            settings = repo / ".claude" / "settings.json"
            bytes_once = settings.read_bytes()
            groups = self._settings(repo)["hooks"]["SessionStart"]
            self.assertEqual(len(groups), 1)
            self.assertIn("codas-managed-hook", groups[0]["hooks"][0]["command"])
            # re-install is a no-op write (idempotent)
            install_claude_session_hook(repo, command="run preflight")
            self.assertEqual(settings.read_bytes(), bytes_once)

    def test_foreign_sessionstart_group_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            settings = repo / ".claude" / "settings.json"
            _write(
                settings,
                json.dumps(
                    {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "mine"}]}]}}
                ),
            )
            install_claude_session_hook(repo, command="run preflight")
            groups = self._settings(repo)["hooks"]["SessionStart"]
            commands = [g["hooks"][0]["command"] for g in groups]
            self.assertIn("mine", commands)  # foreign untouched
            self.assertTrue(any("codas-managed-hook" in c for c in commands))

    def test_malformed_settings_not_clobbered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            settings = repo / ".claude" / "settings.json"
            _write(settings, "{not json")
            result = install_claude_session_hook(repo, command="run preflight")
            self.assertEqual(result.status, "malformed")
            self.assertEqual(settings.read_text(), "{not json")  # untouched


class InstallStateTests(unittest.TestCase):
    def test_install_agent_injection_writes_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "config.yml", "version: 1\n")  # marks a Codas repo
            result = install_agent_injection(repo, command="run preflight")
            state = read_install_state(repo)
            self.assertEqual(state["schema_version"], 1)
            self.assertIn("session_start", state["agent_hooks"]["claude"])
            self.assertEqual(
                state["agent_hooks"]["claude"]["session_start"]["trusted"], "unknown"
            )
            self.assertIn(result.agents_block, ("current", "stale", "absent"))

    def test_install_state_excluded_from_walk_scan(self) -> None:
        """BLOCKER#1: the machine-local marker never enters the inventory scan (walk path)."""
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "x = 1\n")
            _write(repo / ".codas" / ".install-state.json", '{"schema_version": 1}\n')
            walked = _walk_files(repo)
            self.assertNotIn(".codas/.install-state.json", walked)
            self.assertIn("src/a.py", walked)


class PreflightDigestTests(unittest.TestCase):
    def _repo(self, repo: Path, related: list[str]) -> None:
        _write(
            repo / ".codas" / "config.yml",
            "version: 1\nworkspace:\n  roots:\n    - .\n"
            "workflow:\n  adapter: trellis\n  root: .trellis\n  task_globs:\n"
            "    - .trellis/tasks/*/task.json\n",
        )
        _write(
            repo / ".codas" / "structure.yml",
            "version: 1\nkind: structure_map\nunits:\n"
            "  pkg:\n    path: src/pkg\n    kind: package\n    owner: Owner\n"
            "    purpose: p\n    canonical_placement: c\n",
        )
        _write(repo / ".codas" / "policies.yml", "version: 1\npolicies:\n  stale_claim:\n    severity: warning\n")
        _write(repo / "src" / "pkg" / "mod.py", "def existing_helper():\n    return 1\n")
        _write(
            repo / ".codas" / "wiki" / "code" / "pkg.md",
            "Why pkg exists.\n\n```atlas:claims\ndefines: src/pkg/mod.py::::existing_helper\n```\n",
        )
        _write(
            repo / ".trellis" / "tasks" / "t1" / "task.json",
            json.dumps({"id": "t1", "status": "in_progress", "relatedFiles": related}),
        )

    def test_digest_from_related_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._repo(repo, related=["src/pkg/mod.py"])
            digest = build_context_pack(repo, task_id="t1")["digest"]
            self.assertEqual([u["id"] for u in digest["affected_units"]], ["pkg"])
            names = {c["name"] for c in digest["reuse_candidates"]}
            self.assertIn("existing_helper", names)
            # advisory why-prose read from the code-wiki SOURCE, claims fence stripped + labelled
            self.assertEqual(digest["advisory_why"]["pkg"], "Why pkg exists.")
            self.assertIn("section 17", digest["advisory_note"])

    def test_no_task_means_no_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._repo(repo, related=["src/pkg/mod.py"])
            self.assertIsNone(build_context_pack(repo)["digest"])

    def test_empty_related_files_empty_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            self._repo(repo, related=[])
            digest = build_context_pack(repo, task_id="t1")["digest"]
            self.assertEqual(digest["affected_units"], [])
            self.assertEqual(digest["reuse_candidates"], [])


class HooksCliTests(unittest.TestCase):
    """Regression: `codas hooks --install` via the CLI. The `--command` flag once collided with
    the subparsers' `dest="command"` (argparse overwrote the selected command with the flag
    value), so the CLI path raised 'unknown command' even though the app function worked."""

    def test_hooks_install_cli_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            _write(repo / ".codas" / "config.yml", "version: 1\n")
            env = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
            result = subprocess.run(
                [
                    sys.executable, "-m", "codas", "hooks", "--install", ".",
                    "--command", "echo check", "--agent-command", "echo preflight",
                ],
                cwd=repo, capture_output=True, text=True, env=env, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("installed pre-commit", result.stdout)
            self.assertIn("claude session hook: installed", result.stdout)
            self.assertTrue((repo / ".claude" / "settings.json").is_file())
            self.assertTrue((repo / ".codas" / ".install-state.json").is_file())


if __name__ == "__main__":
    unittest.main()
