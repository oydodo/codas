from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codas.app.inventory import render_inventory_json, run_inventory
from codas.core.provenance import inventory_hash
from codas.facts.openworld import open_world_gaps

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


# --- Block A: neutral Codas knowledge-tree emitter ------------------------------
#
# Projects the verified symbol/call/ownership facts into a hierarchical, navigable
# KNOWLEDGE TREE in a NEUTRAL, versioned Codas schema (`codas.knowledge_tree/v1`) — the
# DETERMINISTIC ORGANIZATION layer: scattered facts (646 symbols + 775 call edges +
# unit ownership) reshaped into a package -> module -> class -> function tree with
# resolution-tagged call adjacency, so a host agent (or a Block-B CodeWiki adapter that
# maps this neutral tree to its private schema) navigates structure rather than scanning
# flat rows. A pure projection of the inventory dict, like `project_atlas_pack`: no LLM,
# no ScanContext re-scan, not in the byte-identical inventory hash. The tree is a sound
# LOWER BOUND (open-world): symbol nodes are the top-level defs, but method nodes are
# CALL-ENDPOINT-DERIVED (the adapter emits only top-level symbols), so absence of a node
# or edge is not proof of absence. The SEMANTIC synthesis layer (LLM narrative) and the
# provenance-calibrator/judge that consume this tree are deferred to W3.

_TREE_SCHEMA = "codas.knowledge_tree/v1"


def _node_id(path: str, cls: str, symbol: str) -> str:
    """The class-precise node address ``<path>::<class-or-empty>::<symbol>``. The empty
    class segment (``path::::name``) is a module-level def; a non-empty segment is a
    method, so a same-name method in another class is a DISTINCT node."""
    return f"{path}::{cls}::{symbol}"


def _parent_dir(path: str) -> str:
    """The containing directory of a repo-relative path (``""`` at the top)."""
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _owner_index(units: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Build the ``(path-prefix, unit id, unit owner)`` table for longest-prefix
    ownership. The repo-root unit path (``.``) normalizes to the empty prefix (the
    least-specific catch-all). Sorted by ``(len, prefix, id)`` for a stable,
    YAML-order-independent table. TIE-BREAK: two distinct prefixes of equal length can
    never both prefix the same path, so a real tie requires two units declaring the SAME
    prefix (a malformed structure.yml); ``_owning`` then keeps the FIRST in this order —
    i.e. the lexicographically-smallest (prefix, id) — deterministically, never YAML
    insertion order."""
    owners = [
        ("" if unit["path"] in (".", "./") else unit["path"], unit["id"], unit["owner"])
        for unit in units
    ]
    owners.sort(key=lambda owner: (len(owner[0]), owner[0], owner[1]))
    return owners


def _owning(path: str, owners: list[tuple[str, str, str]]) -> tuple[str | None, str | None]:
    """Longest-prefix owner of ``path`` -> ``(unit_id, unit_owner)`` (``(None, None)`` if
    unowned). Sibling-prefix-safe (``path == prefix`` or ``startswith(prefix + "/")``) so
    unit ``src/codas/app`` never wrongly owns ``src/codas/apple.py``. The strict
    ``len(prefix) > best_len`` keeps the FIRST entry at the winning length (see
    ``_owner_index`` for the deterministic same-prefix tie-break)."""
    best: tuple[str | None, str | None] = (None, None)
    best_len = -1
    for prefix, unit_id, unit_owner in owners:
        matches = prefix == "" or path == prefix or path.startswith(prefix + "/")
        if matches and len(prefix) > best_len:
            best_len = len(prefix)
            best = (unit_id, unit_owner)
    return best


def project_atlas_tree(inventory: dict[str, Any]) -> dict[str, Any]:
    """Project an inventory dict into the neutral Codas knowledge tree (pure, no I/O).

    The deterministic ORGANIZATION layer. Reads three fact families from the inventory:
    top-level symbol defs (class/function nodes), the call graph (resolution-tagged
    ``calls_out``/``calls_in`` edges + CALL-ENDPOINT-DERIVED method nodes the symbol
    extractor cannot surface), and structure units (longest-prefix ``unit_id`` /
    ``unit_owner`` per node). Symbols are authoritative for ``kind`` so a class called as
    a constructor stays a ``class``, never relabelled a ``function``. Every list sorts on
    an explicit total key and the tree is keyed by node-id, so the shape is
    self-determined and byte-identical. ``build_atlas_tree`` only adds the
    ``source_inventory_hash`` on top.
    """
    symbols = (inventory.get("symbols") or {}).get("definitions") or []
    call_edges = (inventory.get("calls") or {}).get("edges") or []
    units = inventory.get("units") or []
    owners = _owner_index(units)

    # node-id -> (path, cls, symbol) and -> kind, for every "::"-bearing node.
    decomp: dict[str, tuple[str, str, str]] = {}
    kinds: dict[str, str] = {}

    def _ensure(path: str, cls: str, symbol: str, kind: str) -> str:
        node_id = _node_id(path, cls, symbol)
        if node_id not in kinds:
            kinds[node_id] = kind
            decomp[node_id] = (path, cls, symbol)
        return node_id

    # 1. Authoritative top-level symbol nodes (class | function), product-scoped.
    for definition in symbols:
        if _in_product(definition["module"]):
            _ensure(definition["module"], "", definition["name"], definition["kind"])

    # 2. Call edges -> endpoint nodes (call-endpoint-derived, lower bound), class
    #    containers for methods, and resolution-tagged adjacency. Only product<->product
    #    edges so the tree stays internal to the product.
    out_edges: dict[str, set[tuple[str, str]]] = {}
    in_edges: dict[str, set[tuple[str, str]]] = {}
    for edge in call_edges:
        caller_path, caller_cls = edge["caller_path"], edge["caller_class"]
        callee_path, callee_cls = edge["callee_path"], edge["callee_class"]
        if not (_in_product(caller_path) and _in_product(callee_path)):
            continue
        caller_id = _ensure(caller_path, caller_cls, edge["caller_symbol"], "function")
        callee_id = _ensure(callee_path, callee_cls, edge["callee_symbol"], "function")
        # A method's enclosing class is its parent node; ensure it exists (a top-level
        # class symbol already created it as a `class` in step 1).
        if caller_cls:
            _ensure(caller_path, "", caller_cls, "class")
        if callee_cls:
            _ensure(callee_path, "", callee_cls, "class")
        # The set deduplicates a call-site repeated in the raw facts; two surviving
        # entries for one (caller, callee) pair mean two distinct resolution tags, both
        # valid (the adapter dedups edges by the 6-tuple, excluding resolution).
        resolution = edge["resolution"]
        out_edges.setdefault(caller_id, set()).add((callee_id, resolution))
        in_edges.setdefault(callee_id, set()).add((caller_id, resolution))

    # 3. Module nodes (one per defining file) and package nodes (every ancestor dir
    #    within product scope, down to the product root `src/codas`).
    module_paths = sorted({path for path, _cls, _symbol in decomp.values()})
    product_root = _PRODUCT_PREFIX.rstrip("/")

    def _in_scope(directory: str) -> bool:
        return directory == product_root or directory.startswith(product_root + "/")

    package_paths: set[str] = set()
    for module_path in module_paths:
        parent = _parent_dir(module_path)
        while _in_scope(parent):
            package_paths.add(parent)
            parent = _parent_dir(parent)

    # 4. Parentage: method -> class, top-level -> module, module -> package,
    #    package -> package.
    children: dict[str, set[str]] = {}
    for node_id, (path, cls, _symbol) in decomp.items():
        parent = _node_id(path, "", cls) if cls else path
        children.setdefault(parent, set()).add(node_id)
    for module_path in module_paths:
        parent = _parent_dir(module_path)
        if _in_scope(parent):
            children.setdefault(parent, set()).add(module_path)
    for package_path in package_paths:
        parent = _parent_dir(package_path)
        if _in_scope(parent):
            children.setdefault(parent, set()).add(package_path)

    def _emit(node_id: str, kind: str, path: str, symbol: str | None) -> dict[str, Any]:
        unit_id, unit_owner = _owning(path, owners)
        return {
            "kind": kind,
            "path": path,
            "symbol": symbol,
            "unit_id": unit_id,
            "unit_owner": unit_owner,
            "children": sorted(children.get(node_id, ())),
            "calls_out": [
                {"target": target, "resolution": resolution}
                for target, resolution in sorted(out_edges.get(node_id, ()))
            ],
            "calls_in": [
                {"source": source, "resolution": resolution}
                for source, resolution in sorted(in_edges.get(node_id, ()))
            ],
        }

    tree: dict[str, dict[str, Any]] = {}
    for node_id, (path, _cls, symbol) in decomp.items():
        tree[node_id] = _emit(node_id, kinds[node_id], path, symbol)
    for module_path in module_paths:
        tree[module_path] = _emit(module_path, "module", module_path, None)
    for package_path in package_paths:
        tree[package_path] = _emit(package_path, "package", package_path, None)

    return {
        "schema": _TREE_SCHEMA,
        # The call graph + call-endpoint method nodes are a sound LOWER BOUND, so a
        # consumer must not read an absent node/edge as proof of absence (open-world).
        "open_world": {
            "is_lower_bound": True,
            "misses": list(open_world_gaps("calls")),
        },
        "tree": tree,
    }


def build_atlas_tree(repo: Path) -> dict[str, Any]:
    """Build the neutral knowledge tree for ``repo`` (projection + source hash).

    Mirrors ``build_atlas_pack``: builds the inventory once with the generated wiki dir
    excluded, projects it, and pins the same ``source_inventory_hash`` freshness anchor —
    so the tree shares the pack's anchor and moves only when the source facts move.
    """
    inventory = run_inventory(repo, exclude_under=(_GENERATED_DIR,))
    tree = project_atlas_tree(inventory)
    tree["source_inventory_hash"] = inventory_hash(render_inventory_json(inventory))
    return tree


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
        # write_bytes (not write_text) pins UTF-8 + LF: text mode would translate "\n" to
        # os.linesep on write, breaking byte-identical on Windows. (Path.write_text gained
        # the `newline` kwarg only in 3.10; this is the 3.9-safe equivalent.)
        page.write_bytes(content.encode("utf-8"))
        written.append(page)
    return sorted(written)


def verify_generated_sections(repo: Path) -> list[Path]:
    """Generated pages whose on-disk bytes differ from a fresh render (stale or
    hand-edited); empty == all up to date.

    The freshness check rides in the bytes: a stale ``source_inventory_hash`` or any
    hand-edit surfaces as a mismatch, so no separate hash bookkeeping is needed. This is
    the home for the source-hash freshness deliberately kept out of the always-on
    ``check`` gate (the committed page's hash churns on every unrelated source change).
    """
    expected = _generated_pages(repo)
    stale: list[Path] = []
    for page, content in expected.items():
        if not page.exists() or page.read_bytes() != content.encode("utf-8"):
            stale.append(page)
    # Orphans: a committed generated/*.md no longer rendered (e.g. a removed section) lingers
    # on disk and regeneration never clears it, so --verify flags it (codex).
    generated_dir = repo / _GENERATED_DIR
    if generated_dir.is_dir():
        for found in generated_dir.glob("*.md"):
            if found not in expected:
                stale.append(found)
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
