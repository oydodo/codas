from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.config.loader import load_codas_config

from .document_loader import load_document_manifest
from .index import build_artifact_index
from .loader import load_structure_map
from .program_loader import load_program_plan

STRUCTURE_SOURCE = ".codas/structure.yml"
PROGRAM_SOURCE = ".codas/program.yml"
DOCUMENTS_SOURCE = ".codas/documents.yml"


def _workspace_roots(config_raw: dict[str, Any]) -> tuple[str, ...]:
    workspace = config_raw.get("workspace")
    if isinstance(workspace, dict):
        roots = workspace.get("roots")
        if isinstance(roots, list) and roots:
            return tuple(str(root) for root in roots)
    return (".",)


def build_inventory(repo: Path) -> dict[str, Any]:
    """Build the deterministic normalized Atlas inventory for a repository.

    Structure portion follows the schema §5 normalized JSON shape (flat at the
    top level); program facts are added as a sibling ``program`` block.
    """
    config = load_codas_config(repo / ".codas" / "config.yml")
    roots = _workspace_roots(config.raw)

    structure_map = load_structure_map(
        repo / ".codas" / "structure.yml", source=STRUCTURE_SOURCE
    )
    index = build_artifact_index(repo, roots, structure_map)

    units = []
    for unit in sorted(structure_map.units, key=lambda item: item.id):
        observed = index.observations[unit.id]
        units.append(
            {
                "id": unit.id,
                "path": unit.path,
                "kind": unit.kind,
                "owner": unit.owner,
                "status": unit.status,
                "claims": [f"claim:structure:{unit.id}:canonical_placement"],
                "observed": {
                    "exists": observed.exists,
                    "artifact_count": observed.artifact_count,
                },
                "must_update_if_changed": list(unit.must_update_if_changed),
            }
        )

    inventory: dict[str, Any] = {
        "schema_version": 1,
        "source": structure_map.source,
        "units": units,
        "conflicts": [],
        "unowned": list(index.unowned),
    }

    program_path = repo / ".codas" / "program.yml"
    if program_path.exists():
        program = load_program_plan(program_path, source=PROGRAM_SOURCE)
        inventory["program"] = {
            "source": program.source,
            "work_items": [
                {
                    "id": item.id,
                    "phase": item.phase,
                    "status": item.status,
                    "depends_on": list(item.depends_on),
                    "trellis_tasks": list(item.trellis_tasks),
                }
                for item in sorted(program.work_items, key=lambda item: item.id)
            ],
        }

    documents_path = repo / ".codas" / "documents.yml"
    if documents_path.exists():
        manifest = load_document_manifest(documents_path, source=DOCUMENTS_SOURCE)
        inventory["documents"] = {
            "source": manifest.source,
            "roles": [
                {
                    "role": document.role,
                    "path": document.path,
                    "authority": document.authority,
                    "owner": document.owner,
                    "observed": {"exists": (repo / document.path).exists()},
                }
                for document in sorted(manifest.documents, key=lambda doc: doc.role)
            ],
        }

    return inventory
