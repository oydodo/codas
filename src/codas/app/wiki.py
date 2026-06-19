from __future__ import annotations

import json
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


# --- D3b: deterministic committed governance page -------------------------------

_GENERATED_PAGE = "governance.md"


def render_generated_overview(
    inventory: dict[str, Any], source_inventory_hash: str
) -> str:
    """Render the committed Atlas governance page from inventory facts (pure, no LLM).

    The readable "governance map" rendering of the live facts: the intended structure
    (units) and plan progress (roadmap), plus a fenced ``atlas:claims`` block carrying
    the ``source_inventory_hash`` and the machine-checkable claims the D3d
    ``generated_wiki_drift`` policy verifies. Deterministic: tables and claim lines
    sort on `id`, no timestamp.

    Dogfood-clean by construction (see adapters/wiki.py + markdown.py): the headings
    (`## Structure Units` / `## Roadmap`) are not claim-creating wiki sections, the
    `atlas:claims` block is fenced (both adapters skip fenced content), and cells carry
    only real, inventory-derived tokens.
    """
    units = sorted(inventory.get("units") or [], key=lambda unit: unit["id"])
    work_items = sorted(
        (inventory.get("program") or {}).get("work_items") or [],
        key=lambda item: item["id"],
    )

    lines = [
        "<!-- GENERATED by `codas wiki --write`. Do not edit by hand; regenerate to refresh. -->",
        "",
        "# Atlas Governance Overview (generated)",
        "",
        f"{_PREAMBLE}. Rendered deterministically from repository facts by",
        "`codas wiki --write`; edit the sources of truth (`.codas/structure.yml`,",
        "`.codas/program.yml`) and regenerate.",
        "",
        "## Structure Units",
        "",
        "| unit | path | kind | owner |",
        "| --- | --- | --- | --- |",
    ]
    for unit in units:
        lines.append(
            "| {} | {} | {} | {} |".format(
                _code(unit["id"]),
                _code(unit["path"]),
                _plain(unit["kind"]),
                _plain(unit["owner"]),
            )
        )

    lines += [
        "",
        "## Roadmap",
        "",
        "| work item | phase | status |",
        "| --- | --- | --- |",
    ]
    for item in work_items:
        lines.append(
            "| {} | {} | {} |".format(
                _code(item["id"]), _plain(item["phase"]), _plain(item["status"])
            )
        )

    lines += ["", "```atlas:claims", f"source_inventory_hash: {source_inventory_hash}"]
    for unit in units:
        lines.append(f"unit: {_claim_token(unit['id'])} -> {_claim_token(unit['path'])}")
    for item in work_items:
        lines.append(
            f"roadmap: {_claim_token(item['id'])} -> {_claim_token(item['status'])}"
        )
    lines += ["```", ""]
    return "\n".join(lines)


def _generated_pages(repo: Path) -> dict[Path, str]:
    """The deterministic ``{path: rendered content}`` for every committed generated
    page — the single render source shared by ``--write`` and ``--verify``.

    Builds the generated-excluded inventory (so the embedded ``source_inventory_hash``
    is stable across writes — the page never feeds its own hash input). The hash pins
    ONLY the exact fields this page renders (each unit's id/path/kind/owner + each
    work-item's id/phase/status), so the page's bytes move exactly when its rendered
    content moves — never on an unrelated source edit (e.g. a unit's volatile
    ``observed.artifact_count`` changing when a file is added under it). Otherwise the
    committed page would restale on every commit and ``--verify`` would be perpetually
    red. (A narrower, more honest freshness anchor than the §4 whole-inventory hash; the
    pack keeps the whole-inventory hash, the page pins its own rendered source.)
    """
    inventory = run_inventory(repo, exclude_under=(_GENERATED_DIR,))
    units = inventory.get("units") or []
    work_items = (inventory.get("program") or {}).get("work_items") or []
    rendered_source = {
        "units": sorted([u["id"], u["path"], u["kind"], u["owner"]] for u in units),
        "roadmap": sorted([w["id"], w["phase"], w["status"]] for w in work_items),
    }
    source_hash = inventory_hash(
        json.dumps(rendered_source, sort_keys=True, separators=(",", ":"), default=str)
    )
    page = repo / _GENERATED_DIR / _GENERATED_PAGE
    return {page: render_generated_overview(inventory, source_hash)}


def write_generated_sections(repo: Path) -> list[Path]:
    """Render and write the committed generated pages; return the written paths.

    Idempotent: identical bytes on a re-run when the source facts are unchanged.
    """
    written: list[Path] = []
    for page, content in _generated_pages(repo).items():
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(content)
        written.append(page)
    return written


def verify_generated_sections(repo: Path) -> list[Path]:
    """Generated pages whose on-disk bytes differ from a fresh render (stale or
    hand-edited); empty == all up to date.

    The freshness check rides in the bytes: a stale ``source_inventory_hash`` or any
    hand-edit surfaces as a mismatch, so no separate hash bookkeeping is needed. This is
    the home for the source-hash freshness deliberately kept out of the always-on
    ``check`` gate (the committed page's hash churns on every unrelated source change).
    """
    stale: list[Path] = []
    for page, content in _generated_pages(repo).items():
        if not page.exists() or page.read_text() != content:
            stale.append(page)
    return sorted(stale)


def _code(value: str) -> str:
    return f"`{_guard_cell(value)}`"


def _plain(value: str) -> str:
    return _guard_cell(value)


def _guard_cell(value: str) -> str:
    """Reject a table cell that would break the markdown table or determinism.

    A `|` or newline in an inventory field is an upstream bug; fail loudly rather than
    silently mangle the rendered table (codex SHOULD — don't assume clean source data).
    """
    if "|" in value or "\n" in value:
        raise ValueError(f"generated table cell breaks the table: {value!r}")
    return value


def _claim_token(value: str) -> str:
    """Reject an atlas:claims token that would break the grammar a D3d parser reads.

    The line grammar is ``key: subject -> value``. A token must not contain the key
    delimiter ``": "`` (colon-space), the subject/value delimiter ``" -> "``/``"->"``,
    or a newline, else the line is ambiguous. (Bare ``:`` without a space is fine, so
    work-item ids like ``program:P0:cli-core`` pass.)
    """
    if "->" in value or ": " in value or "\n" in value or value.startswith("```"):
        raise ValueError(f"atlas:claims token breaks the grammar: {value!r}")
    return value
