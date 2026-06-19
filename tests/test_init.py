"""codas init: scaffold a minimal valid .codas/ skeleton."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.app.doctor import doctor_has_failures, run_doctor
from codas.app.init import scaffold
from codas.config.loader import load_codas_config, load_policies, load_waivers
from codas.structure.loader import load_structure_map

_REQUIRED = (
    ".codas/config.yml",
    ".codas/policies.yml",
    ".codas/structure.yml",
    ".codas/waivers.yml",
)


class InitTests(unittest.TestCase):
    def test_scaffold_writes_the_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            result = scaffold(repo)
            self.assertEqual(result.written, _REQUIRED)
            self.assertEqual(result.skipped, ())
            for rel in _REQUIRED:
                self.assertTrue((repo / rel).exists(), rel)

    def test_scaffolded_templates_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scaffold(repo)
            # Each template must parse through its loader (no schema errors).
            load_codas_config(repo / ".codas" / "config.yml")
            load_policies(repo / ".codas" / "policies.yml")
            load_waivers(repo / ".codas" / "waivers.yml")
            load_structure_map(repo / ".codas" / "structure.yml", source=".codas/structure.yml")

    def test_scaffolded_repo_passes_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scaffold(repo)
            diagnostics = run_doctor(repo)
            self.assertFalse(
                doctor_has_failures(diagnostics),
                [d for d in diagnostics if d.status == "fail"],
            )

    def test_idempotent_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scaffold(repo)
            (repo / ".codas" / "config.yml").write_text("version: 1\nmine: true\n")
            result = scaffold(repo)  # no force
            self.assertEqual(result.written, ())
            self.assertEqual(result.skipped, _REQUIRED)
            self.assertEqual((repo / ".codas" / "config.yml").read_text(), "version: 1\nmine: true\n")

    def test_symlinked_target_file_skipped_not_clobbered(self) -> None:
        # A symlinked .codas/config.yml (even dangling) must be treated as present and
        # never written through to an out-of-repo target.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".codas").mkdir()
            outside = repo / "outside.yml"  # a dangling-ish external target
            (repo / ".codas" / "config.yml").symlink_to(outside)
            result = scaffold(repo)  # no force
            self.assertIn(".codas/config.yml", result.skipped)
            self.assertTrue((repo / ".codas" / "config.yml").is_symlink())
            self.assertFalse(outside.exists())  # never written through the link

    def test_symlinked_codas_dir_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            real = repo / "elsewhere"
            real.mkdir()
            (repo / ".codas").symlink_to(real)
            result = scaffold(repo)
            self.assertEqual(result.written, ())
            self.assertEqual(set(result.skipped), set(_REQUIRED))
            self.assertEqual(list(real.iterdir()), [])  # nothing written into the target

    def test_force_replaces_symlink_with_real_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".codas").mkdir()
            outside = repo / "outside.yml"
            (repo / ".codas" / "config.yml").symlink_to(outside)
            scaffold(repo, force=True)
            self.assertFalse((repo / ".codas" / "config.yml").is_symlink())
            self.assertFalse(outside.exists())  # the link was dropped, not followed
            self.assertIn("constraint_sources", (repo / ".codas" / "config.yml").read_text())

    def test_force_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scaffold(repo)
            (repo / ".codas" / "config.yml").write_text("clobbered\n")
            result = scaffold(repo, force=True)
            self.assertEqual(result.written, _REQUIRED)
            self.assertIn("constraint_sources", (repo / ".codas" / "config.yml").read_text())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
