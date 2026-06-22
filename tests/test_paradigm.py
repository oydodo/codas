"""codas init --paradigm: preset data model, loading, render + ecosystem honesty (S3)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.app.check import run_check
from codas.app.init import _STRUCTURE, scaffold
from codas.app.paradigm import (
    PresetError,
    detect_ecosystems,
    is_advisory,
    list_presets,
    load_preset,
    render_paradigm,
)
from codas.structure.loader import load_structure_map

_BUILTINS = ("clean-arch", "ddd", "layered")


def _git_repo(tmp: str, *, marker: str = "pyproject.toml", body: str = "[project]\n") -> Path:
    repo = Path(tmp)
    (repo / marker).write_text(body)
    return repo


class PresetLoadTests(unittest.TestCase):
    def test_builtins_load_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for name in _BUILTINS:
                preset = load_preset(repo, name)
                self.assertEqual(preset.name, name)
                self.assertEqual(preset.source, "builtin")
                self.assertTrue(preset.roles)
                self.assertIn(preset.top_level, ("layers", "contexts"))
                self.assertTrue(preset.enforceable_for)

    def test_ddd_is_contexts_shaped_with_cross_context_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset = load_preset(Path(tmp), "ddd")
            self.assertEqual(preset.top_level, "contexts")
            self.assertEqual(preset.cross_context, "published-interface")
            self.assertEqual(
                [r.id for r in preset.roles],
                ["domain", "application", "adapters", "infrastructure"],
            )

    def test_local_preset_shadows_builtin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "clean-arch.yml").write_text(
                "name: clean-arch\n"
                "description: Local override.\n"
                "enforceable_for: [python]\n"
                "top_level: layers\n"
                "roles:\n"
                "  - {id: core, must_not_depend_on: [], purpose: P., canonical_placement: C.}\n"
            )
            preset = load_preset(repo, "clean-arch")
            self.assertEqual(preset.source, "local")
            self.assertEqual(preset.description, "Local override.")
            self.assertEqual([r.id for r in preset.roles], ["core"])

    def test_unknown_name_raises_with_available_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PresetError) as ctx:
                load_preset(Path(tmp), "nope")
            self.assertIn("clean-arch", str(ctx.exception))

    def test_unknown_edge_target_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "bad.yml").write_text(
                "name: bad\n"
                "description: D.\n"
                "enforceable_for: [python]\n"
                "top_level: layers\n"
                "roles:\n"
                "  - {id: a, must_not_depend_on: [ghost], purpose: P., canonical_placement: C.}\n"
            )
            with self.assertRaises(PresetError) as ctx:
                load_preset(repo, "bad")
            self.assertIn("ghost", str(ctx.exception))

    def test_missing_required_field_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "bad.yml").write_text(
                "name: bad\n"
                "description: D.\n"
                "enforceable_for: [python]\n"
                "top_level: layers\n"
                "roles:\n"
                "  - {id: a, must_not_depend_on: [], purpose: P.}\n"  # no canonical_placement
            )
            with self.assertRaises(PresetError):
                load_preset(repo, "bad")

    def test_scalar_must_not_depend_on_rejected(self) -> None:
        # A scalar where a list is expected must raise, not silently drop the edge.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "bad.yml").write_text(
                "name: bad\n"
                "description: D.\n"
                "enforceable_for: [python]\n"
                "top_level: layers\n"
                "roles:\n"
                "  - {id: a, must_not_depend_on: b, purpose: P., canonical_placement: C.}\n"
                "  - {id: b, must_not_depend_on: [], purpose: P., canonical_placement: C.}\n"
            )
            with self.assertRaises(PresetError):
                load_preset(repo, "bad")

    def test_name_must_match_filename_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "myfile.yml").write_text(
                "name: different\n"
                "description: D.\n"
                "enforceable_for: [python]\n"
                "top_level: layers\n"
                "roles:\n"
                "  - {id: a, must_not_depend_on: [], purpose: P., canonical_placement: C.}\n"
            )
            with self.assertRaises(PresetError):
                load_preset(repo, "myfile")

    def test_miskeyed_role_list_rejected(self) -> None:
        # A contexts preset must use `layers:`; using `roles:` is a hard error (no fallback).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "ctx.yml").write_text(
                "name: ctx\n"
                "description: D.\n"
                "enforceable_for: [python]\n"
                "top_level: contexts\n"
                "roles:\n"  # wrong key for a contexts preset
                "  - {id: a, must_not_depend_on: [], purpose: P., canonical_placement: C.}\n"
            )
            with self.assertRaises(PresetError):
                load_preset(repo, "ctx")


class RenderTests(unittest.TestCase):
    def test_clean_arch_renders_expected_units_and_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset = load_preset(Path(tmp), "clean-arch")
        rendered = render_paradigm(preset)
        self.assertEqual(
            list(rendered.units),
            [
                "example_context-domain",
                "example_context-application",
                "example_context-adapters",
                "example_context-infrastructure",
            ],
        )
        domain = rendered.units["example_context-domain"]
        self.assertEqual(domain["path"], "src/example_context/domain")
        self.assertEqual(domain["kind"], "layer")
        self.assertEqual(domain["status"], "planned")
        self.assertEqual(
            rendered.dependency_rules["example_context-domain"]["must_not_depend_on"],
            [
                "example_context-application",
                "example_context-adapters",
                "example_context-infrastructure",
            ],
        )
        # Innermost-outermost: infrastructure forbids nothing -> no rule entry.
        self.assertNotIn("example_context-infrastructure", rendered.dependency_rules)

    def test_render_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset = load_preset(Path(tmp), "ddd")
        from codas.app.paradigm import render_structure_yaml

        self.assertEqual(
            render_structure_yaml(render_paradigm(preset)),
            render_structure_yaml(render_paradigm(preset)),
        )

    def test_advisory_marks_units_and_prose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preset = load_preset(Path(tmp), "clean-arch")
        rendered = render_paradigm(preset, advisory=True)
        self.assertTrue(rendered.advisory)
        self.assertIn("ADVISORY", rendered.prose)
        self.assertIn(
            "ADVISORY",
            rendered.units["example_context-domain"]["canonical_placement"],
        )


class EcosystemTests(unittest.TestCase):
    def test_python_repo_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _git_repo(tmp)
            self.assertIn("python", detect_ecosystems(repo))

    def test_node_only_is_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _git_repo(tmp, marker="package.json", body="{}\n")
            eco = detect_ecosystems(repo)
            self.assertEqual(eco, {"node"})
            preset = load_preset(repo, "clean-arch")
            self.assertTrue(is_advisory(preset, eco))

    def test_python_repo_enforceable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _git_repo(tmp)
            preset = load_preset(repo, "clean-arch")
            self.assertFalse(is_advisory(preset, detect_ecosystems(repo)))

    def test_stray_py_does_not_flip_node_repo_to_python(self) -> None:
        # Marker-only: an incidental .py in a Node repo must not present the preset as enforced.
        with tempfile.TemporaryDirectory() as tmp:
            repo = _git_repo(tmp, marker="package.json", body="{}\n")
            (repo / "tools.py").write_text("print('helper')\n")
            eco = detect_ecosystems(repo)
            self.assertEqual(eco, {"node"})
            self.assertTrue(is_advisory(load_preset(repo, "clean-arch"), eco))


class ListTests(unittest.TestCase):
    def test_lists_builtins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = [n for n, _, _ in list_presets(Path(tmp))]
            self.assertEqual(names, list(_BUILTINS))

    def test_local_overrides_source_in_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            presets_dir = repo / ".codas" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "clean-arch.yml").write_text(
                "name: clean-arch\n"
                "description: Mine.\n"
                "enforceable_for: [python]\n"
                "top_level: layers\n"
                "roles:\n"
                "  - {id: core, must_not_depend_on: [], purpose: P., canonical_placement: C.}\n"
            )
            entry = {n: (d, s) for n, d, s in list_presets(repo)}["clean-arch"]
            self.assertEqual(entry, ("Mine.", "local"))


class ScaffoldIntegrationTests(unittest.TestCase):
    def test_paradigm_none_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            scaffold(repo, paradigm="none")
            self.assertEqual(
                (repo / ".codas" / "structure.yml").read_text(), _STRUCTURE
            )

    def test_paradigm_seeds_planned_units_and_check_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _git_repo(tmp)
            result = scaffold(repo, paradigm="clean-arch")
            self.assertEqual(result.paradigm, "clean-arch")
            self.assertFalse(result.advisory)  # python repo -> enforceable
            structure = load_structure_map(
                repo / ".codas" / "structure.yml", source=".codas/structure.yml"
            )
            ids = {u.id for u in structure.units}
            self.assertIn("root", ids)  # catch-all preserved
            self.assertIn("example_context-domain", ids)
            planned = {u.id for u in structure.units if u.status == "planned"}
            self.assertEqual(len(planned), 4)
            # GREEN: no error findings (placeholder paths -> dependency_direction inert,
            # planned -> structure_drift exempt). Warnings (dogfooding) are allowed.
            report = run_check(repo)
            errors = [f for f in report.findings if f.severity == "error"]
            self.assertEqual(errors, [], [f.check_id for f in errors])

    def test_paradigm_no_clobber_does_not_report_seeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _git_repo(tmp)
            (repo / ".codas").mkdir()
            (repo / ".codas" / "structure.yml").write_text("version: 1\nmine: true\n")
            result = scaffold(repo, paradigm="clean-arch")  # no force
            self.assertIn(".codas/structure.yml", result.skipped)
            self.assertEqual(
                (repo / ".codas" / "structure.yml").read_text(), "version: 1\nmine: true\n"
            )
            # Honesty: nothing was seeded, so don't report a paradigm/advisory (no false
            # "seeded ..." CLI line next to the skip line).
            self.assertIsNone(result.paradigm)
            self.assertFalse(result.advisory)

    def test_unknown_paradigm_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            with self.assertRaises(PresetError):
                scaffold(repo, paradigm="bogus")
            self.assertFalse((repo / ".codas").exists())  # atomic: failed before writing


if __name__ == "__main__":
    unittest.main()
