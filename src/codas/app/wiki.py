from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.app.inventory import render_inventory_json, run_inventory
from codas.core.provenance import inventory_hash

# Source code the pack scopes its symbol/dependency views to (the product, not the
# vendored .trellis/scripts or tests). NB the inventory `symbols`/`imports` `module`
# fields are repo-relative PATHS, not dotted names, so this is a path prefix.
_PRODUCT_PREFIX = "src/codas/"

# Inventory facts derived from generated wiki pages must be excluded from the hash a
# generated page pins (the inventory ingests `.codas/wiki/`; embedding the full hash
# would be self-referential). See build_inventory(exclude_under=...).
_GENERATED_DIR = ".codas/wiki/generated"

_PREAMBLE = "VERIFIED GOVERNANCE FACTS (prefer over inferred structure)"


def project_atlas_pack(inventory: dict[str, Any]) -> dict[str, Any]:
    """Project an inventory dict into the Atlas grounding pack (pure, no I/O).

    The "FEED" half of the wiki architecture: the verified facts a host agent (or an
    OSS LLM-wiki tool) should prefer over its own inferred structure. A pure function
    of the inventory so the pack is a derived view, never a second source of truth —
    `build_atlas_pack` only adds the `source_inventory_hash` on top. Every projected
    list uses an explicit total sort key (never inventory/dict insertion order) so the
    pack shape is self-determined and deterministic.
    """
    symbols = (inventory.get("symbols") or {}).get("definitions") or []
    imports = (inventory.get("imports") or {}).get("edges") or []
    units = inventory.get("units") or []
    wiki_claims = (inventory.get("wiki_claims") or {}).get("claims") or []
    work_items = (inventory.get("program") or {}).get("work_items") or []

    dependency_graph = sorted(
        (
            {
                "module": edge["module"],
                "target": edge["target"],
                "target_path": edge["target_path"],
            }
            for edge in imports
            # first-party edges from product code: scoped to src/codas like
            # symbol_index, so the pack describes the product's dependencies (not the
            # vendored .trellis/scripts internal edges).
            if edge.get("target_path") and _in_product(edge["module"])
        ),
        key=lambda edge: (edge["module"], edge["target_path"], edge["target"]),
    )

    symbol_index = sorted(
        (
            {
                "module": definition["module"],
                "name": definition["name"],
                "kind": definition["kind"],
                "line": definition["line"],
            }
            for definition in symbols
            if _in_product(definition["module"])
        ),
        key=lambda item: (item["module"], item["line"], item["name"], item["kind"]),
    )

    ownership = sorted(
        (
            {
                "id": unit["id"],
                "path": unit["path"],
                "kind": unit["kind"],
                "owner": unit["owner"],
            }
            for unit in units
        ),
        key=lambda unit: unit["id"],
    )

    concept_index = sorted(
        (
            {
                "concept": claim["concept"],
                "path": claim["path"],
                "exists": claim["exists"],
            }
            for claim in wiki_claims
            if claim.get("kind") == "concept_page"
        ),
        key=lambda claim: (claim["path"], claim["concept"]),
    )

    verified_evidence = sorted(
        (
            {
                "source": claim["source"],
                "concept": claim["concept"],
                "kind": claim["kind"],
                "path": claim["path"],
            }
            for claim in wiki_claims
            if claim.get("exists") is True
        ),
        key=lambda claim: (claim["source"], claim["kind"], claim["path"], claim["concept"]),
    )

    roadmap = sorted(
        (
            {"id": item["id"], "phase": item["phase"], "status": item["status"]}
            for item in work_items
        ),
        key=lambda item: item["id"],
    )

    return {
        "preamble": _PREAMBLE,
        "dependency_graph": dependency_graph,
        "symbol_index": symbol_index,
        "ownership": ownership,
        "concept_index": concept_index,
        "verified_evidence": verified_evidence,
        "roadmap": roadmap,
    }


def build_atlas_pack(repo: Path) -> dict[str, Any]:
    """Build the Atlas grounding pack for ``repo`` (projection + source hash).

    Builds the inventory once with the generated wiki dir excluded, projects it, and
    pins a `source_inventory_hash` over that same excluded inventory — so the hash a
    generated page later embeds is stable against editing the generated pages and moves
    only when the underlying source facts move.
    """
    inventory = run_inventory(repo, exclude_under=(_GENERATED_DIR,))
    pack = project_atlas_pack(inventory)
    pack["source_inventory_hash"] = inventory_hash(render_inventory_json(inventory))
    return pack


def _in_product(module: str) -> bool:
    """True if a symbol/import `module` path is under the product source tree."""
    return module == _PRODUCT_PREFIX.rstrip("/") or module.startswith(_PRODUCT_PREFIX)
