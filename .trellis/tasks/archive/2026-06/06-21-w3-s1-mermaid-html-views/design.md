# Design — W3·S1 mermaid + html deterministic views

DETERMINISTIC, no LLM, NOT gate semantics (no policy / no check wiring / not in the inventory
hash) → no codex DESIGN review required; codex IMPL review at the end. Pure projections off
already-verified facts — "borrow CodeWiki's mermaid + html, the Codas way".

## Surfaces (two new wiki_mode flags, siblings of --emit-tree)
- `codas wiki --emit-mermaid` → a Mermaid `graph` of the PRODUCT module dependency graph,
  printed to stdout. Source = the Atlas pack `dependency_graph` (module -> target_path import
  edges, product-scoped via the shipped `_in_product`). Bounded (~tens of modules), readable.
- `codas wiki --emit-html` → a self-contained static HTML page (stdout) embedding (a) the
  open-world caveat banner, (b) the Mermaid diagram, (c) a navigable list of the knowledge
  tree (packages → modules → symbols, with unit ownership). Pure projection of build_atlas_tree
  + the dependency graph.

## Open-world caveat MUST be rendered into the output (critic finding — load-bearing)
A dependency diagram that hides "this is a sound LOWER BOUND; absence ≠ denial" re-imports
CodeWiki's false-completeness failure at the PRESENTATION layer, even though the underlying
facts are sound. So:
- mermaid: a `%%` comment line + a VISIBLE note node (a labelled box) carrying the lower-bound
  caveat + the named `open_world_gaps("calls"|"imports")` misses.
- html: a banner `<div>` with the caveat text + the misses list, above the diagram.
Mirror the note `codas impact` already prints.

## Determinism / §11 / §17
- New module `src/codas/app/views.py`: `build_mermaid(repo) -> str`, `build_html(repo) -> str`,
  pure projections; imports build_atlas_tree/build_atlas_pack (app→app) + open_world_gaps
  (facts) — NO adapter import. Every node/edge list sorted on an explicit total key.
- Out of the inventory hash (stdout only, like --emit-pack/--emit-tree). The HTML may reference
  a mermaid.js CDN for client-side rendering, but the EMITTED BYTES are fully deterministic
  (the CDN is a view-time convenience, not part of the artifact's determinism).
- Mermaid label/id escaping: node ids derived from module paths must be sanitized to a stable
  mermaid-safe token (deterministic mapping); labels with special chars quoted. A guard like
  `_guard_cell` rejects/escapes anything that would break the diagram or determinism.

## Test plan
- build_mermaid / build_html byte-identical across two runs (run-twice), on the live repo.
- the open-world caveat string IS present in both outputs (assert the misses appear).
- CLI --emit-mermaid / --emit-html exit 0 + mutual exclusion (SystemExit 2) with other wiki modes.
- a small synthetic dependency_graph → expected mermaid edges (projection-logic), sanitization
  of a path with special chars.
- §11/§17: views.py imports no adapter; no LLM; not in the inventory hash (check . 0, byte-identical).

## Out of scope
- S3 (judge), S2 (multi-lang). No LLM rendering. No committed artifact (stdout only; a
  `--write`-style committed view is a later option, would follow the generated-page out-of-hash
  pattern).
