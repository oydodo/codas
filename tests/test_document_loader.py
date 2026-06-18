from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codas.config.loader import CodasConfig, load_codas_config
from codas.policies.document_set import check_document_set
from codas.structure.document_loader import (
    DocumentManifestError,
    load_document_manifest,
)

VALID = """\
version: 1
kind: document_role_manifest
defaults:
  authority: authoritative
required_roles:
  - plan
documents:
  plan:
    path: docs/plan.html
    owner: Doc Steward
    updates_when: [scope_changes]
  readme:
    path: README.md
    authority: supporting
    owner: Core
    updates_when: [usage_changes]
"""


def _load(text: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "documents.yml"
        path.write_text(text)
        return load_document_manifest(path, source="documents.yml")


def _write_manifest(repo: Path, body: str) -> None:
    (repo / ".codas").mkdir(parents=True, exist_ok=True)
    (repo / ".codas" / "documents.yml").write_text(body)


class DocumentLoaderTests(unittest.TestCase):
    def test_valid_loads(self) -> None:
        manifest = _load(VALID)
        self.assertEqual(len(manifest.documents), 2)
        plan = next(d for d in manifest.documents if d.role == "plan")
        self.assertEqual(plan.authority, "authoritative")  # defaults applied
        self.assertEqual(plan.updates_when, ("scope_changes",))
        self.assertEqual(manifest.required_roles, ("plan",))

    def test_real_repo_manifest_loads(self) -> None:
        manifest = load_document_manifest(
            Path.cwd() / ".codas" / "documents.yml", source=".codas/documents.yml"
        )
        self.assertIn("implementation_plan", manifest.role_ids())

    def test_missing_version_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("version: 1\n", "", 1))

    def test_bad_kind_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("document_role_manifest", "other"))

    def test_missing_path_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("    path: docs/plan.html\n", "", 1))

    def test_bad_authority_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("    authority: supporting\n", "    authority: bogus\n"))

    def test_missing_owner_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("    owner: Doc Steward\n", "", 1))

    def test_empty_updates_when_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("    updates_when: [scope_changes]\n", "    updates_when: []\n"))

    def test_non_string_trigger_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("[scope_changes]", "[123]"))

    def test_required_role_not_declared_raises(self) -> None:
        with self.assertRaises(DocumentManifestError):
            _load(VALID.replace("  - plan\n", "  - ghost\n", 1))


class DocumentSetPolicyTests(unittest.TestCase):
    def test_real_repo_has_no_findings(self) -> None:
        config = load_codas_config(Path.cwd() / ".codas" / "config.yml")
        self.assertEqual(check_document_set(Path.cwd(), config), [])

    def test_canonical_role_not_required_yields_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "README.md").write_text("x")
            _write_manifest(
                repo,
                "version: 1\nkind: document_role_manifest\nrequired_roles: []\n"
                "documents:\n  readme:\n    path: README.md\n"
                "    authority: supporting\n    owner: Core\n    updates_when: [usage_changes]\n",
            )
            config = CodasConfig(path=repo / ".codas" / "config.yml", raw={})
            findings = check_document_set(repo, config)

            self.assertIn("implementation_plan", " ".join(f.message for f in findings))
            self.assertTrue(all(f.check_id == "document-set-complete" for f in findings))

    def test_missing_target_file_yields_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            _write_manifest(
                repo,
                "version: 1\nkind: document_role_manifest\nrequired_roles: []\n"
                "documents:\n  ghost:\n    path: docs/missing.html\n"
                "    authority: authoritative\n    owner: Core\n    updates_when: [x]\n",
            )
            config = CodasConfig(path=repo / ".codas" / "config.yml", raw={})
            findings = check_document_set(repo, config)
            self.assertTrue(any("missing file" in f.message for f in findings))

    def test_authority_conflict_yields_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "docs").mkdir(parents=True, exist_ok=True)
            (repo / "docs" / "x.html").write_text("x")
            _write_manifest(
                repo,
                "version: 1\nkind: document_role_manifest\nrequired_roles: []\n"
                "documents:\n  product_design:\n    path: docs/x.html\n"
                "    authority: supporting\n    owner: Core\n    updates_when: [a]\n",
            )
            config = CodasConfig(
                path=repo / ".codas" / "config.yml",
                raw={},
                authoritative_sources=("docs/x.html",),
            )
            findings = check_document_set(repo, config)
            self.assertTrue(any("conflicts with config" in f.message for f in findings))


if __name__ == "__main__":
    unittest.main()
