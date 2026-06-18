from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.structure.loader import StructureMapError, load_structure_map

VALID_MAP = """\
version: 1
kind: structure_map
metadata:
  project: Demo
defaults:
  status: active
roles:
  core: Core
units:
  root:
    path: .
    kind: repository
    owner: Core
    purpose: Root workspace.
    canonical_placement: Root metadata lives here.
    allowed_children:
      - app
  app:
    path: src/app
    kind: package
    owner: Core
    purpose: Application code.
    canonical_placement: App code lives here.
    must_update_if_changed:
      - docs/x.md
dependency_rules:
  app:
    may_depend_on:
      - root
deprecated_paths:
  old:
    path: src/old
    status: removed
    replacement: src/app
"""


def _load(text: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "structure.yml"
        path.write_text(text)
        return load_structure_map(path, source="structure.yml")


class StructureLoaderTests(unittest.TestCase):
    def test_valid_map_loads(self) -> None:
        structure_map = _load(VALID_MAP)
        self.assertEqual(structure_map.version, 1)
        self.assertEqual(structure_map.unit_ids(), frozenset({"root", "app"}))
        self.assertEqual(structure_map.roles, {"core": "Core"})
        self.assertEqual(len(structure_map.deprecated_paths), 1)
        self.assertEqual(structure_map.deprecated_paths[0].replacement, "src/app")
        self.assertEqual(structure_map.dependency_rules[0].may_depend_on, ("root",))

    def test_real_repo_map_loads(self) -> None:
        structure_map = load_structure_map(
            Path.cwd() / ".codas" / "structure.yml", source=".codas/structure.yml"
        )
        self.assertIn("codas-source", structure_map.unit_ids())

    def test_missing_version_raises(self) -> None:
        with self.assertRaises(StructureMapError):
            _load(VALID_MAP.replace("version: 1\n", "", 1))

    def test_bad_kind_raises(self) -> None:
        with self.assertRaises(StructureMapError):
            _load(VALID_MAP.replace("kind: structure_map", "kind: something_else"))

    def test_unit_missing_owner_raises(self) -> None:
        broken = VALID_MAP.replace("    owner: Core\n    purpose: Application code.\n", "    purpose: Application code.\n")
        with self.assertRaises(StructureMapError):
            _load(broken)

    def test_dangling_allowed_child_raises(self) -> None:
        broken = VALID_MAP.replace("      - app\n", "      - app\n      - ghost\n")
        with self.assertRaises(StructureMapError):
            _load(broken)

    def test_invalid_status_raises(self) -> None:
        broken = VALID_MAP.replace(
            "    canonical_placement: App code lives here.\n",
            "    canonical_placement: App code lives here.\n    status: imaginary\n",
        )
        with self.assertRaises(StructureMapError):
            _load(broken)

    def test_dangling_dependency_target_raises(self) -> None:
        broken = VALID_MAP.replace("      - root\n", "      - nowhere\n")
        with self.assertRaises(StructureMapError):
            _load(broken)

    def test_non_mapping_dependency_rule_raises(self) -> None:
        broken = VALID_MAP.replace(
            "dependency_rules:\n  app:\n    may_depend_on:\n      - root\n",
            "dependency_rules:\n  app: not-a-mapping\n",
        )
        with self.assertRaises(StructureMapError):
            _load(broken)

    def test_duplicate_top_level_key_raises(self) -> None:
        with self.assertRaises(StructureMapError):
            _load("version: 1\n" + VALID_MAP)


if __name__ == "__main__":
    unittest.main()
