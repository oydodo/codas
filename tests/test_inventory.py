from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codas.app.inventory import render_inventory_json
from codas.config.loader import CodasConfig
from codas.policies.program_plan import check_program_plan
from codas.policies.structure_map import check_structure_map
from codas.structure.inventory import build_inventory


class InventoryTests(unittest.TestCase):
    def test_inventory_is_deterministic(self) -> None:
        repo = Path.cwd()
        first = render_inventory_json(build_inventory(repo))
        second = render_inventory_json(build_inventory(repo))
        self.assertEqual(first, second)

    def test_inventory_shape(self) -> None:
        inventory = build_inventory(Path.cwd())
        self.assertEqual(inventory["schema_version"], 1)
        self.assertEqual(inventory["source"], ".codas/structure.yml")
        self.assertEqual(inventory["conflicts"], [])

        ids = {unit["id"] for unit in inventory["units"]}
        self.assertIn("codas-source", ids)
        for unit in inventory["units"]:
            self.assertIn("exists", unit["observed"])
            self.assertIn("artifact_count", unit["observed"])

        self.assertIn("program", inventory)
        self.assertEqual(len(inventory["program"]["work_items"]), 8)

        self.assertIn("documents", inventory)
        roles = {role["role"] for role in inventory["documents"]["roles"]}
        self.assertIn("implementation_plan", roles)
        for role in inventory["documents"]["roles"]:
            self.assertIn("exists", role["observed"])

        self.assertIn("doc_claims", inventory)
        self.assertIn("references", inventory["doc_claims"])
        for ref in inventory["doc_claims"]["references"]:
            self.assertIn("exists", ref)

        self.assertIn("tasks", inventory)
        self.assertEqual(inventory["tasks"]["source_root"], ".trellis/tasks")
        self.assertTrue(inventory["tasks"]["items"])

    def test_json_serializable(self) -> None:
        # Guards against datetime.date leaking from YAML metadata.
        json.dumps(build_inventory(Path.cwd()))


class StructureMapPolicyTests(unittest.TestCase):
    def test_malformed_structure_map_yields_error_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            structure = repo / ".codas" / "structure.yml"
            structure.parent.mkdir(parents=True, exist_ok=True)
            structure.write_text("version: 1\nkind: structure_map\nunits: {}\n")

            config = CodasConfig(path=repo / ".codas" / "config.yml", raw={})
            findings = check_structure_map(repo, config)

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].check_id, "structure-map-loads")
            self.assertEqual(findings[0].severity, "error")

    def test_valid_repo_structure_map_has_no_findings(self) -> None:
        config = CodasConfig(path=Path.cwd() / ".codas" / "config.yml", raw={})
        self.assertEqual(check_structure_map(Path.cwd(), config), [])


class ProgramPlanPolicyTests(unittest.TestCase):
    def test_malformed_program_plan_yields_error_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            program = repo / ".codas" / "program.yml"
            program.parent.mkdir(parents=True, exist_ok=True)
            program.write_text(
                "version: 1\nkind: program_plan\n"
                "work_items:\n  - id: bad-id\n    phase: P0\n    title: X\n    status: planned\n"
            )

            config = CodasConfig(path=repo / ".codas" / "config.yml", raw={})
            findings = check_program_plan(repo, config)

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].check_id, "program-plan-loads")
            self.assertEqual(findings[0].severity, "error")

    def test_valid_repo_program_plan_has_no_findings(self) -> None:
        config = CodasConfig(path=Path.cwd() / ".codas" / "config.yml", raw={})
        self.assertEqual(check_program_plan(Path.cwd(), config), [])


if __name__ == "__main__":
    unittest.main()
