from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.adapters.trellis import extract_task_facts
from codas.config.loader import load_codas_config
from codas.facts.context import ScanContext
from codas.facts.soundness import FACT_SOUNDNESS

from .document_loader import load_document_manifest
from .index import build_artifact_index, discover_files, workspace_roots
from .loader import load_structure_map
from .program_loader import load_program_plan

STRUCTURE_SOURCE = ".codas/structure.yml"
PROGRAM_SOURCE = ".codas/program.yml"
DOCUMENTS_SOURCE = ".codas/documents.yml"


def build_inventory(
    repo: Path,
    exclude_under: tuple[str, ...] = (),
    ctx: ScanContext | None = None,
) -> dict[str, Any]:
    """Build the deterministic normalized Atlas inventory for a repository.

    Structure portion follows the schema §5 normalized JSON shape (flat at the
    top level); program facts are added as a sibling ``program`` block.

    The file-scoped facts (doc claims, symbols, imports, wiki claims, calls) are
    PROJECTED from a single :class:`~codas.facts.context.ScanContext` — the same
    fact-provider the policy engine consumes — so a run scans (and parses) once. The
    inventory is the structure/planning projection of that shared scan plus the
    Trellis task facts (trellis-rooted, not file-scoped).

    ``ctx`` lets a caller that already built a ScanContext (``check --json`` for its
    provenance block) reuse it instead of triggering a second scan. When ``ctx`` is
    given it is authoritative: it already carries the resolved config/roots/files
    (any ``exclude_under`` is assumed already applied to it) and ``exclude_under`` is
    ignored.

    ``exclude_under`` (self-built path only) drops tracked files under the given
    repo-relative directory prefixes from the scanned file set BEFORE the
    ScanContext is built, so Python import/call resolution — which depends on the
    file set — and the artifact index both see the filtered set. It must pre-filter,
    never post-filter rows. Default ``()`` performs no filtering, so ``codas
    inventory`` / provenance stay byte-identical. The Atlas pack
    (``app/wiki.build_atlas_pack``) passes ``(".codas/wiki/generated",)`` so the
    ``source_inventory_hash`` it pins is not self-referential (the inventory ingests
    ``.codas/wiki/``; a generated page that embeds the full inventory hash would chase
    its own bytes). NB ``extract_task_facts`` is trellis-rooted, not file-scoped, so
    the ``tasks`` block is unaffected — harmless, since the excluded dir only holds
    ``.md``.
    """
    if ctx is None:
        config = load_codas_config(repo / ".codas" / "config.yml")
        roots = workspace_roots(config.raw)
        files = discover_files(repo, roots)
        if exclude_under:
            files = [
                path
                for path in files
                if not any(
                    path == prefix or path.startswith(prefix + "/")
                    for prefix in exclude_under
                )
            ]
        ctx = ScanContext(repo=repo, config=config, roots=roots, files=tuple(files))
    else:
        config = ctx.config
        roots = ctx.roots

    files = list(ctx.files)
    structure_map = load_structure_map(
        repo / ".codas" / "structure.yml", source=STRUCTURE_SOURCE
    )
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

    doc_claims = ctx.doc_claims()
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

    html_claims = ctx.html_claims()
    inventory["html_claims"] = {
        "sources": sorted({claim.source for claim in html_claims}),
        "references": [
            {
                "source": claim.source,
                "line": claim.line,
                "path": claim.path,
                "fragment": claim.fragment,
                "kind": claim.kind,
                "exists": claim.exists,
            }
            for claim in html_claims
        ],
    }

    wiki_claims = ctx.wiki_claims()
    inventory["wiki_claims"] = {
        "sources": sorted({claim.source for claim in wiki_claims.claims}),
        "claims": [
            {
                "source": claim.source,
                "line": claim.line,
                "concept": claim.concept,
                "kind": claim.kind,
                "path": claim.path,
                "path_kind": claim.path_kind,
                "exists": claim.exists,
            }
            for claim in wiki_claims.claims
        ],
        "skipped": list(wiki_claims.skipped),
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

    symbols = ctx.symbols()
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

    imports = ctx.imports()
    inventory["imports"] = {
        "sources": sorted({fact.module for fact in imports.imports}),
        "edges": [
            {
                "module": fact.module,
                "target": fact.target,
                "target_path": fact.target_path,
                "line": fact.line,
            }
            for fact in imports.imports
        ],
        "skipped": list(imports.skipped),
    }

    call_facts = ctx.calls()
    inventory["calls"] = {
        "sources": sorted({edge.caller_path for edge in call_facts.edges}),
        "edges": [
            {
                "caller_module": edge.caller_module,
                "caller_class": edge.caller_class,
                "caller_symbol": edge.caller_symbol,
                "caller_path": edge.caller_path,
                "caller_line": edge.caller_line,
                "callee_module": edge.callee_module,
                "callee_class": edge.callee_class,
                "callee_symbol": edge.callee_symbol,
                "callee_path": edge.callee_path,
                "callee_line": edge.callee_line,
                "resolution": edge.resolution,
            }
            for edge in call_facts.edges
        ],
        "skipped": list(call_facts.skipped),
    }

    # fact_soundness: a STATIC per-family soundness manifest (B2) — a sibling of the
    # symbols/imports/calls blocks declaring, per family, the sensor's level + scope +
    # named under-approximations. A frozen constant, so adding it changes the inventory
    # hash exactly once, then stays byte-identical run-to-run; the existing fact blocks
    # are untouched (no per-row field), so their rows stay byte-identical too. ``level``
    # serializes as its lowercase name (never the int rank) and every list is sorted.
    inventory["fact_soundness"] = {
        family: FACT_SOUNDNESS[family].as_dict() for family in sorted(FACT_SOUNDNESS)
    }

    return inventory
