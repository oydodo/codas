from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.facts.context import build_scan_context
from codas.policies.dependency_direction import check_dependency_direction


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _unit(uid: str, path: str) -> str:
    return textwrap.dedent(
        f"""\
        {uid}:
            path: {path}
            kind: module
            owner: X
            purpose: p
            canonical_placement: c
        """
    )


def _structure(repo: Path, units: dict[str, str], rules: dict[str, list[str]]) -> None:
    body = "version: 1\nkind: structure_map\nunits:\n"
    for uid, path in units.items():
        body += textwrap.indent(_unit(uid, path), "  ")
    if rules:
        body += "dependency_rules:\n"
        for unit, forbidden in rules.items():
            body += f"  {unit}:\n    must_not_depend_on:\n"
            body += "".join(f"      - {fid}\n" for fid in forbidden)
    _write(repo / ".codas" / "structure.yml", body)


def _findings(repo: Path):
    ctx = build_scan_context(repo, CodasConfig(path=repo / ".codas" / "config.yml", raw={}))
    return check_dependency_direction(ctx)


UNITS = {"repo-root": ".", "pol": "src/pol", "adp": "src/adp"}


class DependencyDirectionPolicyTests(unittest.TestCase):
    def test_forbidden_import_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _structure(repo, UNITS, {"pol": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "p.py", "import adp.a\n")
            _write(repo / "src" / "adp" / "__init__.py", "")
            _write(repo / "src" / "adp" / "a.py", "x = 1\n")

            findings = _findings(repo)

            self.assertEqual(len(findings), 1)
            finding = findings[0]
            self.assertEqual(finding.check_id, "dependency-direction")
            self.assertEqual(finding.severity, "error")
            self.assertEqual(finding.meta["importer_unit"], "pol")
            self.assertEqual(finding.meta["forbidden_unit"], "adp")
            self.assertEqual(finding.evidence[0].path, "src/pol/p.py")
            self.assertEqual(finding.evidence[1].path, "src/adp/a.py")

    def test_allowed_first_party_import_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            units = {**UNITS, "util": "src/util"}
            _structure(repo, units, {"pol": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "p.py", "import util.u\n")
            _write(repo / "src" / "util" / "__init__.py", "")
            _write(repo / "src" / "util" / "u.py", "x = 1\n")

            self.assertEqual(_findings(repo), [])

    def test_external_import_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _structure(repo, UNITS, {"pol": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "p.py", "import os\nimport sys\n")

            self.assertEqual(_findings(repo), [])

    def test_rules_are_local_not_inherited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            # The PARENT unit (src) forbids adp; pol is a child unit with no rule.
            units = {"repo-root": ".", "src-unit": "src", "pol": "src/pol", "adp": "src/adp"}
            _structure(repo, units, {"src-unit": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "p.py", "import adp.a\n")
            _write(repo / "src" / "adp" / "__init__.py", "")
            _write(repo / "src" / "adp" / "a.py", "x = 1\n")

            # p.py is owned by pol (most specific); pol declares no rule -> no finding.
            self.assertEqual(_findings(repo), [])

    def test_descendant_target_under_forbidden_unit_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _structure(repo, UNITS, {"pol": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "p.py", "import adp.sub.deep\n")
            _write(repo / "src" / "adp" / "__init__.py", "")
            _write(repo / "src" / "adp" / "sub" / "__init__.py", "")
            _write(repo / "src" / "adp" / "sub" / "deep.py", "x = 1\n")

            findings = _findings(repo)

            self.assertEqual([f.meta["target_path"] for f in findings], ["src/adp/sub/deep.py"])

    def test_intra_unit_import_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _structure(repo, UNITS, {"pol": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "p.py", "import pol.q\n")
            _write(repo / "src" / "pol" / "q.py", "x = 1\n")

            self.assertEqual(_findings(repo), [])

    def test_findings_sorted_by_module_line_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _structure(repo, UNITS, {"pol": ["adp"]})
            _write(repo / "src" / "pol" / "__init__.py", "")
            _write(repo / "src" / "pol" / "b.py", "import adp.a\n")
            _write(repo / "src" / "pol" / "a.py", "import adp.a\n")
            _write(repo / "src" / "adp" / "__init__.py", "")
            _write(repo / "src" / "adp" / "a.py", "x = 1\n")

            modules = [f.evidence[0].path for f in _findings(repo)]

            self.assertEqual(modules, ["src/pol/a.py", "src/pol/b.py"])

    def test_real_adapter_boundary_layout_fires(self) -> None:
        # Mirror the actual repo layout/names: codas-policies must_not_depend_on
        # codas-adapters. Proves the dogfood rule has teeth end-to-end, not just the
        # toy pol/adp paths.
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            units = {
                "repo-root": ".",
                "codas-source": "src/codas",
                "codas-policies": "src/codas/policies",
                "codas-adapters": "src/codas/adapters",
            }
            _structure(repo, units, {"codas-policies": ["codas-adapters"]})
            _write(repo / "src" / "codas" / "__init__.py", "")
            _write(repo / "src" / "codas" / "policies" / "__init__.py", "")
            _write(repo / "src" / "codas" / "policies" / "evil.py", "import codas.adapters.python\n")
            _write(repo / "src" / "codas" / "adapters" / "__init__.py", "")
            _write(repo / "src" / "codas" / "adapters" / "python.py", "x = 1\n")

            findings = _findings(repo)

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].meta["importer_unit"], "codas-policies")
            self.assertEqual(findings[0].meta["forbidden_unit"], "codas-adapters")
            self.assertEqual(findings[0].evidence[0].path, "src/codas/policies/evil.py")
            self.assertEqual(findings[0].evidence[1].path, "src/codas/adapters/python.py")

    def test_missing_structure_map_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "pol" / "p.py", "import adp.a\n")

            self.assertEqual(_findings(repo), [])


if __name__ == "__main__":
    unittest.main()
