from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.facts.context import ScanContext, build_scan_context
from codas.policies.duplicate_implementation import check_duplicate_implementation


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


def _ctx(repo: Path) -> ScanContext:
    return build_scan_context(repo, _config(repo))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _claims(*entries: str) -> str:
    body = "".join(entries) or "  []\n"
    return "version: 1\nkind: claim_set\nduplicate_relationships:\n" + body


def _claim(symbol: str, modules: list[str], relationship: str = "variant") -> str:
    block = (
        f"  - symbol: {symbol}\n"
        f"    relationship: {relationship}\n"
        f"    owner: Core\n"
        f"    reason: intentional\n"
        f"    modules:\n"
    )
    return block + "".join(f"      - {module}\n" for module in modules)


class DuplicateImplementationPolicyTests(unittest.TestCase):
    def test_public_and_private_undeclared_duplicates_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n\n\ndef _helper():\n    pass\n")
            _write(repo / "src" / "b.py", "def handle():\n    pass\n\n\ndef _helper():\n    pass\n")

            findings = check_duplicate_implementation(_ctx(repo))

            self.assertEqual({f.check_id for f in findings}, {"duplicate-implementation"})
            self.assertEqual([f.meta["name"] for f in findings], ["_helper", "handle"])
            self.assertTrue(all(f.severity == "error" for f in findings))

    def test_declared_relationship_suppresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def _helper():\n    pass\n\n\ndef other():\n    pass\n")
            _write(repo / "src" / "b.py", "def _helper():\n    pass\n\n\ndef other():\n    pass\n")
            _write(
                repo / ".codas" / "claims.yml",
                _claims(_claim("_helper", ["src/a.py", "src/b.py"])),
            )

            findings = check_duplicate_implementation(_ctx(repo))

            # _helper claimed for exactly these modules → suppressed; other errors
            self.assertEqual([f.meta["name"] for f in findings], ["other"])

    def test_claim_with_different_module_set_does_not_suppress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def dup():\n    pass\n")
            _write(repo / "src" / "b.py", "def dup():\n    pass\n")
            # claim covers a different module set → must NOT suppress the real dup
            _write(
                repo / ".codas" / "claims.yml",
                _claims(_claim("dup", ["src/a.py", "src/c.py"])),
            )

            findings = check_duplicate_implementation(_ctx(repo))

            self.assertEqual([f.meta["name"] for f in findings], ["dup"])

    def test_claim_missing_modules_is_schema_error_and_does_not_suppress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def dup():\n    pass\n")
            _write(repo / "src" / "b.py", "def dup():\n    pass\n")
            _write(
                repo / ".codas" / "claims.yml",
                "version: 1\nkind: claim_set\nduplicate_relationships:\n"
                "  - symbol: dup\n    relationship: variant\n    owner: Core\n    reason: y\n",
            )

            ids = [f.check_id for f in check_duplicate_implementation(_ctx(repo))]

            # one schema error for the modules-less claim, and dup is still flagged
            self.assertEqual(ids, ["claim-schema-invalid", "duplicate-implementation"])

    def test_single_module_and_out_of_scope_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def only():\n    pass\n")
            _write(repo / "tests" / "x.py", "def helper():\n    pass\n")
            _write(repo / "tests" / "y.py", "def helper():\n    pass\n")
            _write(repo / ".trellis" / "scripts" / "p.py", "def go():\n    pass\n")
            _write(repo / ".trellis" / "scripts" / "q.py", "def go():\n    pass\n")

            self.assertEqual(check_duplicate_implementation(_ctx(repo)), [])

    def test_missing_claims_file_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / "src" / "a.py", "def dup():\n    pass\n")
            _write(repo / "src" / "b.py", "def dup():\n    pass\n")

            findings = check_duplicate_implementation(_ctx(repo))

            self.assertEqual([f.meta["name"] for f in findings], ["dup"])

    def test_relationships_not_a_list_is_schema_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "claims.yml", "version: 1\nkind: claim_set\nduplicate_relationships: nope\n")

            findings = check_duplicate_implementation(_ctx(repo))

            self.assertEqual([f.check_id for f in findings], ["claim-schema-invalid"])

    def test_invalid_relationship_value_and_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(
                repo / ".codas" / "claims.yml",
                "version: 1\nkind: claim_set\nduplicate_relationships:\n"
                "  - symbol: x\n    relationship: bogus\n    owner: Core\n    reason: y\n"
                "  - relationship: variant\n    owner: Core\n    reason: y\n",
            )

            ids = [f.check_id for f in check_duplicate_implementation(_ctx(repo))]

            self.assertEqual(ids, ["claim-schema-invalid", "claim-schema-invalid"])

    def test_malformed_yaml_is_load_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write(repo / ".codas" / "claims.yml", "version: 1\n  bad: indent\n")

            findings = check_duplicate_implementation(_ctx(repo))

            self.assertEqual([f.check_id for f in findings], ["claims-load-error"])


if __name__ == "__main__":
    unittest.main()
