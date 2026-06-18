from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.document_loader import (
    DocumentManifestError,
    load_document_manifest,
)

DOCUMENTS_SOURCE = ".codas/documents.yml"

# Document roles Codas core depends on; a governed manifest must mark these
# required so they cannot be silently dropped. The loader already enforces that
# every required role is declared with an existing path.
CANONICAL_REQUIRED_ROLES = frozenset(
    {
        "product_design",
        "implementation_plan",
        "structure_map_schema",
        "structure_map",
        "program_plan",
        "policy_set",
        "config",
    }
)


def check_document_set(repo: Path, config: CodasConfig) -> list[Finding]:
    """Verify the Document Role Manifest and Project Document Set (document_set_complete).

    Checks: the manifest loads; the canonical required roles are marked required;
    every declared role's path exists on disk; and each role whose path is a
    verbatim entry in config.yml constraint_sources carries the matching
    authority. A missing manifest is reported by check_config_sources (it is a
    declared source).
    """
    path = repo / ".codas" / "documents.yml"
    if not path.exists():
        return []

    try:
        manifest = load_document_manifest(path, source=DOCUMENTS_SOURCE)
    except DocumentManifestError as error:
        return [
            Finding(
                severity="error",
                check_id="document-set-complete",
                message=str(error),
                evidence=[Evidence(path=DOCUMENTS_SOURCE)],
                recommendation="Fix the Document Role Manifest so it parses and declares all required roles.",
            )
        ]

    findings: list[Finding] = []
    required = set(manifest.required_roles)

    for canonical in sorted(CANONICAL_REQUIRED_ROLES - required):
        findings.append(
            Finding(
                severity="error",
                check_id="document-set-complete",
                message=f"canonical document role {canonical!r} is not marked required",
                evidence=[Evidence(path=DOCUMENTS_SOURCE)],
                recommendation="Add the canonical role to required_roles in documents.yml.",
            )
        )

    authoritative = set(config.authoritative_sources)
    supporting = set(config.supporting_sources)

    for document in manifest.documents:
        if not (repo / document.path).exists():
            findings.append(
                Finding(
                    severity="error",
                    check_id="document-set-complete",
                    message=f"document role {document.role!r} points at a missing file: {document.path}",
                    evidence=[Evidence(path=document.path)],
                )
            )
            continue

        expected = (
            "authoritative"
            if document.path in authoritative
            else "supporting"
            if document.path in supporting
            else None
        )
        if expected is not None and document.authority != expected:
            findings.append(
                Finding(
                    severity="error",
                    check_id="document-set-complete",
                    message=(
                        f"document role {document.role!r} authority {document.authority!r} "
                        f"conflicts with config.yml constraint_sources ({expected})"
                    ),
                    evidence=[Evidence(path=document.path)],
                    recommendation="Align documents.yml authority with config.yml constraint_sources.",
                )
            )

    return findings
