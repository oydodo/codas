from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.config.loader import ConfigLoadError, load_yaml_mapping

from .models import DOCUMENT_AUTHORITIES, DocumentManifest, DocumentRole


class DocumentManifestError(RuntimeError):
    """Raised when the Document Role Manifest cannot be loaded or is malformed.

    Maps to the `document_set_complete` policy.
    """

    def __init__(self, message: str, source: str) -> None:
        super().__init__(message)
        self.source = source


def load_document_manifest(path: Path, source: str | None = None) -> DocumentManifest:
    src = source or path.name

    try:
        raw = load_yaml_mapping(path)
    except ConfigLoadError as error:
        raise DocumentManifestError(str(error), src) from error

    version = raw.get("version")
    if not isinstance(version, int):
        raise DocumentManifestError("document manifest missing integer 'version'", src)
    kind = raw.get("kind")
    if kind != "document_role_manifest":
        raise DocumentManifestError(
            f"document manifest 'kind' must be 'document_role_manifest', got {kind!r}",
            src,
        )
    documents_raw = raw.get("documents")
    if not isinstance(documents_raw, dict) or not documents_raw:
        raise DocumentManifestError("document manifest has no 'documents' mapping", src)

    defaults = _mapping(raw.get("defaults"))
    default_authority = defaults.get("authority")

    documents: list[DocumentRole] = []
    for role, body in documents_raw.items():
        if not isinstance(body, dict):
            raise DocumentManifestError(f"document {role!r} is not a mapping", src)

        doc_path = body.get("path")
        if not isinstance(doc_path, str) or not doc_path.strip():
            raise DocumentManifestError(f"document {role!r} missing 'path'", src)

        authority = body.get("authority", default_authority)
        if authority not in DOCUMENT_AUTHORITIES:
            raise DocumentManifestError(
                f"document {role!r} has invalid authority {authority!r}", src
            )

        owner = body.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            raise DocumentManifestError(f"document {role!r} missing 'owner'", src)

        updates_when = body.get("updates_when")
        if not isinstance(updates_when, list) or not updates_when:
            raise DocumentManifestError(
                f"document {role!r} requires a non-empty 'updates_when' list", src
            )
        triggers: list[str] = []
        for trigger in updates_when:
            if not isinstance(trigger, str) or not trigger.strip():
                raise DocumentManifestError(
                    f"document {role!r} has an empty/non-string update trigger", src
                )
            triggers.append(trigger)

        documents.append(
            DocumentRole(
                role=str(role),
                path=doc_path,
                authority=str(authority),
                owner=owner,
                updates_when=tuple(triggers),
            )
        )

    role_ids = {document.role for document in documents}
    required_roles = _str_tuple(raw.get("required_roles"))
    for required in required_roles:
        if required not in role_ids:
            raise DocumentManifestError(
                f"required_roles names undeclared role {required!r}", src
            )

    return DocumentManifest(
        version=version,
        kind=kind,
        documents=tuple(documents),
        required_roles=required_roles,
        source=src,
        metadata=_mapping(raw.get("metadata")),
        defaults=defaults,
    )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if item is not None)
    return ()
