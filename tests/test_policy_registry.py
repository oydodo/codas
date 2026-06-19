"""policy_registry: .codas/policies.yml declarations <-> implemented check_* policies.

Fixtures inject symbol facts into a temp ScanContext and write a temp policies.yml, so
no top-level `check_*` is ever defined in a repo-scanned file (that would perturb the
real registry / the dogfood-0 test).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig, load_codas_config
from codas.facts.context import ScanContext, SymbolFact, SymbolFacts, build_scan_context
from codas.policies.policy_registry import check_policy_registry


def _ctx(tmp: Path, symbols, policies_yaml: str) -> ScanContext:
    (tmp / ".codas").mkdir(parents=True, exist_ok=True)
    (tmp / ".codas" / "policies.yml").write_text(policies_yaml)
    config = CodasConfig(path=tmp / ".codas" / "config.yml", raw={})
    ctx = ScanContext(repo=tmp, config=config, roots=(), files=())
    ctx._cache["symbols"] = SymbolFacts(tuple(symbols), ())
    return ctx


def _check(module: str, name: str) -> SymbolFact:
    return SymbolFact(module=module, name=name, kind="function", line=1)


class PolicyRegistryTests(unittest.TestCase):
    def test_zero_on_this_repo(self) -> None:
        # The reconciled registry is consistent: every implemented check declared,
        # every declared non-planned policy implemented.
        repo = Path.cwd()
        ctx = build_scan_context(repo, load_codas_config(repo / ".codas" / "config.yml"))
        self.assertEqual(check_policy_registry(ctx), [])

    def test_implemented_but_undeclared_fires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [_check("src/codas/policies/foo.py", "check_foo")],
                "version: 1\npolicies: {}\n",
            )
            findings = check_policy_registry(ctx)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].severity, "error")
            self.assertEqual(findings[0].check_id, "policy-registry")
            self.assertIn("check_foo", findings[0].message)
            self.assertEqual(findings[0].evidence[0].path, "src/codas/policies/foo.py")

    def test_declared_but_unimplemented_fires(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [],
                "version: 1\npolicies:\n  bar:\n    severity: error\n",
            )
            findings = check_policy_registry(ctx)
            self.assertEqual(len(findings), 1)
            self.assertIn("bar", findings[0].message)
            self.assertEqual(findings[0].evidence[0].path, ".codas/policies.yml")

    def test_status_planned_exempts_unimplemented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [],
                "version: 1\npolicies:\n  bar:\n    severity: error\n    status: planned\n",
            )
            self.assertEqual(check_policy_registry(ctx), [])

    def test_declared_and_implemented_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [_check("src/codas/policies/foo.py", "check_foo")],
                "version: 1\npolicies:\n  foo:\n    severity: error\n    kind: bootstrap\n",
            )
            self.assertEqual(check_policy_registry(ctx), [])

    def test_non_policy_symbols_are_out_of_scope(self) -> None:
        # A non-check_ helper under policies/, and a check_* OUTSIDE policies/, must
        # neither count as implemented nor be required to be declared.
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [
                    _check("src/codas/policies/foo.py", "helper"),
                    _check("tests/test_x.py", "check_outside"),
                    _check(".trellis/scripts/common/paths.py", "check_path"),
                ],
                "version: 1\npolicies: {}\n",
            )
            self.assertEqual(check_policy_registry(ctx), [])

    def test_id_is_function_name_not_module_filename(self) -> None:
        # missing_owner.py defines check_missing_structure_owner -> id is the function
        # name; a declaration under the filename would NOT satisfy it.
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [_check("src/codas/policies/missing_owner.py", "check_missing_structure_owner")],
                "version: 1\npolicies:\n  missing_structure_owner:\n    severity: error\n",
            )
            self.assertEqual(check_policy_registry(ctx), [])

    def test_non_string_policy_keys_are_ignored_not_crash(self) -> None:
        # A YAML int key (`1:`) is not a policy id; it must be dropped, not crash the
        # mixed-type sort (codex impl-review NIT).
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [_check("src/codas/policies/foo.py", "check_foo")],
                "version: 1\npolicies:\n  1:\n    severity: error\n  foo:\n    severity: error\n",
            )
            self.assertEqual(check_policy_registry(ctx), [])

    def test_malformed_policies_yaml_returns_empty(self) -> None:
        # run_check owns the policy-load-error finding; the policy must not double-report.
        with tempfile.TemporaryDirectory() as tmp:
            ctx = _ctx(
                Path(tmp),
                [_check("src/codas/policies/foo.py", "check_foo")],
                "version: 1\n  bad: indent\n",
            )
            self.assertEqual(check_policy_registry(ctx), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
