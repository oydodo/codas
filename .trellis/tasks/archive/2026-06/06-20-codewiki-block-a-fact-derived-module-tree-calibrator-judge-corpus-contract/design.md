# Design — Block A neutral Codas knowledge-tree emitter (revised; PRD+design only)

Converged after codex review (4 BLOCKERs) + the user's organization-value rebuttal. Block A =
ONLY the deterministic ORGANIZATION layer (a neutral knowledge-tree emitter). Semantic synthesis
+ provenance-anchoring + judge = W3 (their consumer). This kills codex #3 (premature build) and
#6 (schema coupling) by construction, and defers #1/#4 to where they're consumed.

## The artifact: a neutral, versioned Codas knowledge tree
A PURE projection of the inventory into a hierarchical knowledge structure Codas OWNS
(IMPLEMENTED — `project_atlas_tree` / `build_atlas_tree` in src/codas/app/wiki.py):
  {
    "schema": "codas.knowledge_tree/v1",
    # freshness anchor pinned by build_atlas_tree (NOT by the pure projector), mirroring
    # build_atlas_pack — same generated-excluded inventory hash, so the tree moves only
    # when the source facts move. Printed to stdout, so it never enters the inventory.
    "source_inventory_hash": "sha256:<hex>",
    # open-world disclosure implementing "the tree is a lower bound, never claimed
    # complete": call edges + call-endpoint method nodes are a sound lower bound.
    "open_world": { "is_lower_bound": true, "misses": [ "<calls gap>", ... ] },
    "tree": { "<node-id>": {
       "kind": "package|module|class|function",   # a method is a `function` child of its class
       "path": "<repo-rel path>",
       "symbol": "<name>|null",            # null for a dir/package node
       "unit_id": "<structure unit id>|null",   # codex: was "owner" — collided with the
       "unit_owner": "<unit human/team owner>|null",  #   unit's human owner; split both out
       "children": [ "<node-id>", ... ],   # deterministic order
       # codex SHOULD-FIX a: call edges are OBJECTS carrying resolution, not bare ids — a
       # bare id would strip the `resolution` tag and mislead W3 about edge confidence.
       "calls_out": [ {"target": "<callee node-id>", "resolution": "direct|imported_symbol|module_attribute|self_method"}, ... ],
       "calls_in":  [ {"source": "<caller node-id>", "resolution": "..."}, ... ]
    } }
  }
- NODE-ID = the class/resolution-PRECISE fact address (codex #1): for a symbol,
  "<repo-rel path>::<class-or-empty>::<name>" (carry caller_class/callee_class from call facts so
  a same-name method in another class is a DISTINCT node). For a dir/module node, the path.
- METHOD NODES (codex SHOULD-FIX b): `ctx.symbols()` emits ONLY top-level class/function defs,
  NOT methods. So method nodes are CALL-ENDPOINT-DERIVED: a node exists for any caller/callee
  the `calls` facts reference (which DO carry class context), as a known LOWER-BOUND set
  (open-world — there may be methods no first-party call reaches). The design states this
  explicitly: symbol nodes = top-level symbol facts ∪ call-endpoint nodes; the tree is a
  lower bound, never claimed complete. (Expanding symbol extraction to methods is a separate
  later option, not Block A.)
- ORGANIZATION = group symbols under their module/dir (hierarchy via path), attach call edges
  (resolution-tagged objects) as calls_out/calls_in between nodes, attach unit_id/unit_owner via
  the Structure Map index's LONGEST-PREFIX ownership (structure/index.py behavior — reuse, don't
  re-derive). This is the "scattered facts -> knowledge system" step, deterministic.
- NEUTRAL SCHEMA (codex #6): this is Codas's OWN shape, versioned, tool-agnostic. Block B's
  CodeWiki adapter MAPS this neutral tree -> CodeWiki's first_module_tree.json
  ({path, components:["file.py::Symbol"], children}); that mapping (and the coupling to an
  unlicensed private schema) lives ENTIRELY in Block B, never in this core.
- DETERMINISTIC: sorted node-ids, sorted children, calls sorted by (target/source, resolution),
  stable nesting; a fixture pins the bytes.
- NOT in the inventory hash (a derived artifact, like the atlas pack). CLI surface (codex NIT —
  DECIDED): **`codas wiki --emit-tree`** (reuse the existing `wiki` command group, mirroring
  `--emit-pack`), prints the JSON; a fixture pins the exact bytes.

## Scope + module-name convention (codex #5 — RESOLVED here, not "at build")
- SCOPE: first-party product code only — reuse the atlas pack's product-scope predicate
  (app/wiki.py `_in_product` / the `src/codas` prefix it already uses); exclude vendored
  `.trellis/scripts`, tests dir, and anything outside the workspace roots. ONE shared helper
  (promote `_in_product` to a documented function; do NOT clone it).
- NODE-ID / module-name CONVENTION: the repo-relative path is the spine (matches how
  symbols.module / calls.*_path are already PATHS, not dotted). A package/dir node id = its
  repo-rel dir path; a symbol node id = "<path>::<class>::<name>". One convention, documented,
  no dotted/​path ambiguity.

## Determinism / §11 / §17
- Pure projection of ctx.symbols()/imports()/calls() + the Structure Map units; no LLM; sorted.
- §11: lives in app/ (projection of inventory, like build_atlas_pack), consuming facts via the
  inventory/ScanContext, importing no adapter.
- Not serialized into the byte-identical inventory (derived artifact). The atlas pack precedent
  (app/wiki.py build_atlas_pack + exclude_under) is the model.

## What this explicitly does NOT do (deferred to W3, per codex #3/#2/#4)
- No semantic synthesis (LLM). No "calibrator" / trust-tier policy. No `codas check` warning.
- No corpus-claim reader / no W1 generalization yet (when the synthesis layer lands, UNIFY the
  reader so W1 `anchor_symbol` becomes the `defines` case — codex #4 — and `check_code_anchor`
  delegates or retires; recorded for W3, not done now).
- The PROVENANCE-anchoring "calibrator" (W3) snaps a synthesis claim to a knowledge-tree node /
  fact (CONFIRMED = matches a present fact, class-precise; UNCONFIRMED = no match, open-world,
  NEVER "false"; SEMANTIC = a capability label with no fact) — as an OFFLINE tag for the judge,
  NOT a gate. This is codex #2's fix (provenance, not trust-stamp) and serves the user's
  grounded-higher-cognition. Recorded; built in W3.

## Sequence
Block A (this) -> W3 (synthesis + provenance-calibrator + judge, consumes the tree) ; Block B
(FSoft CodeWiki shell-out, maps the neutral tree to CodeWiki schema, license-gated) is independent
and later. Per [[never-skip-trellis-for-low-risk]]: even though Block A is pure projection (no
gate), going to BUILD it still goes through Trellis start -> impl -> codex impl review -> commit
-> archive. (No code this round.)
