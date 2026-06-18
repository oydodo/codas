from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.adapters.markdown import extract_doc_claims
from codas.adapters.python import extract_symbol_facts
from codas.adapters.trellis import extract_task_facts
from codas.config.loader import load_codas_config

from .document_loader import load_document_manifest
from .index import build_artifact_index, discover_files, workspace_roots
from .loader import load_structure_map
from .program_loader import load_program_plan

STRUCTURE_SOURCE = ".codas/structure.yml"
PROGRAM_SOURCE = ".codas/program.yml"
DOCUMENTS_SOURCE = ".codas/documents.yml"


def build_inventory(repo: Path) -> dict[str, Any]:
    """Build the deterministic normalized Atlas inventory for a repository.

    Structure portion follows the schema §5 normalized JSON shape (flat at the
    top level); program facts are added as a sibling ``program`` block.
    """
    config = load_codas_config(repo / ".codas" / "config.yml")
    roots = workspace_roots(config.raw)

    structure_map = load_structure_map(
        repo / ".codas" / "structure.yml", source=STRUCTURE_SOURCE
    )
    files = discover_files(repo, roots)
    index = build_artifact_index(repo, roots, structure_map, files=files)

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

    doc_claims = extract_doc_claims(repo, tuple(files))
    inventory["doc_claims"] = {
        "sources": sorted({claim.source for claim in doc_claims}),
        "references": [
            {
                "source": claim.source,
                "line": claim.line,
                "path": claim.path,
                "fragment": claim.fragment,
                "kind": claim.kind,
                "exists": claim.exists,
            }
            for claim in doc_claims
        ],
    }

    task_facts = extract_task_facts(repo, config)
    inventory["tasks"] = {
        "source_root": task_facts.source_root,
        "items": [
            {
                "id": task.id,
                "status": task.status,
                "package": task.package,
                "dev_type": task.dev_type,
                "priority": task.priority,
                "archived": task.archived,
            }
            for task in task_facts.items
        ],
        "skipped": list(task_facts.skipped),
    }

    symbols = extract_symbol_facts(repo, tuple(files))
    inventory["symbols"] = {
        "sources": sorted({definition.module for definition in symbols.definitions}),
        "definitions": [
            {
                "module": definition.module,
                "name": definition.name,
                "kind": definition.kind,
                "line": definition.line,
            }
            for definition in symbols.definitions
        ],
        "skipped": list(symbols.skipped),
    }

    return inventory
