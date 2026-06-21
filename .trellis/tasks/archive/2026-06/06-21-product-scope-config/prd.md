# Config-drive product scope (_PRODUCT_PREFIX) — cross-repo enabler

## Goal

Remove the hardcoded `_PRODUCT_PREFIX = "src/codas/"` (`src/codas/app/wiki.py:14`) that scopes
the knowledge tree / pack / book / feed to Codas's OWN layout. Make it config-driven so the
wiki outputs cover ANY repo's product code — the real "works on another repo" enabler (deeper
than W8 packaging: `pip install` lets you RUN Codas elsewhere, but the book/tree/pack come out
EMPTY until product scope is configurable).

## Background

`_in_product(module)` (wiki.py:143) gates which symbols/call-edges/packages enter the DERIVED
outputs: `project_atlas_pack` (symbol_index, dependency_graph), `project_atlas_tree` (symbol +
method nodes, call adjacency, package ancestry), and via them the book (`book.py`), views, and
the W3 feed/calibrator. On a non-`src/codas/` repo, `_in_product` returns False for everything
→ 0 nodes → empty book/pack/tree.

NOT gate-semantics: the byte-identical INVENTORY is NOT product-scoped (704 symbol defs total,
only 290 under src/codas) — `_in_product` touches ONLY derived, out-of-hash outputs. So this is
an app-layer scope refactor (codex IMPL review; no DESIGN review required). The book/pack/tree
are deterministic renders — their freshness is `--verify`; this change must keep Codas's own
outputs BYTE-IDENTICAL (Codas's effective scope stays `src/codas`).

OUT OF SCOPE: the 2nd hardcoding `_POLICY_PREFIX = "src/codas/policies/"` (policy_registry.py:8)
— that gates the Codas-SELF dogfood check "every check_* policy is declared"; it is
self-specific (another repo has no Codas policy registry to verify), so leave it.

## Design

- **Config knob:** `wiki.product_roots` (list of repo-relative path prefixes; sits beside
  `wiki.enabled/path`). Resolver `product_roots(raw)` (mirrors `workspace_roots`), default
  `("src",)` when unset — the common src-layout convention (a flat-layout repo configures its
  package dir explicitly; documented).
- **Codas's own `.codas/config.yml`:** set `wiki.product_roots: ["src/codas"]` EXPLICITLY.
  Required for byte-identical: a bare `("src",)` would add a `src` package node + reshuffle
  ancestry/ownership (NOT identical). With `["src/codas"]` the scope == today's `src/codas/`.
- **One predicate:** `_in_product(module)` + the tree's internal `_in_scope(directory)` both
  reduce to "path == root OR startswith(root + '/') for any root" → collapse into a single
  `_under_any(path, roots)` helper; `_PRODUCT_PREFIX` constant removed.
- **Thread `product_roots` as DATA** (pure projections stay pure):
  - `project_atlas_pack(inventory, product_roots)` + `project_atlas_tree(inventory,
    product_roots)` gain the param (used by `_in_product`/`_in_scope`/the package-root climb at
    wiki.py:270-298, generalized to multi-root).
  - `build_atlas_pack(repo)` / `build_atlas_tree(repo)` LOAD config → compute `product_roots`
    → pass. (They already build the inventory; add a config read.)
  - `book.py`: `project_book(inventory, prose_by_unit, product_roots)`; `book_pages(repo)` reads
    config → passes. (book.py calls `project_atlas_tree` directly.)
  - views.py + calibrate.py consume `build_atlas_*` → unchanged (config read happens inside).
  - cli.py `--emit-pack/-tree` use `build_atlas_*(repo)` → unchanged.

## Requirements

- R1 — `wiki.product_roots` config knob + `product_roots(raw)` resolver (default `("src",)`).
- R2 — `_in_product`/tree scope are multi-root, config-driven; `_PRODUCT_PREFIX` removed.
- R3 — Codas `config.yml` sets `["src/codas"]`; the book/pack/tree/feed are BYTE-IDENTICAL to
  HEAD (proven: `wiki --verify` clean + emit-pack/tree diff-empty vs HEAD).
- R4 — a synthetic non-src/codas repo (e.g. product at `lib/`) with `product_roots: ["lib"]`
  yields a NON-empty tree covering `lib/**` — proving cross-repo scoping works.

## Acceptance Criteria

- [ ] `_PRODUCT_PREFIX` gone; `_in_product` reads configured roots (multi-root).
- [ ] Codas book/pack/tree byte-identical to HEAD (`wiki --verify` clean; emit-pack/tree
      unchanged); `codas check` == 0; inventory byte-identical 2×; full suite green.
- [ ] Default `("src",)` works unconfigured for a src-layout repo; `["lib"]` scopes a lib-layout.
- [ ] New tests: `product_roots` resolver default/override; tree/pack scoped to configured roots
      (a synthetic `lib/` repo renders a non-empty tree); Codas-scope parity.

## Notes

- App-layer (derived outputs only, out-of-hash) → codex IMPL review; full Trellis rhythm.
- This is ONE of the cross-repo blockers; full cross-repo use also needs W7 (book existence)
  + W8 (packaging) + per-repo scaffolding maturity. Chain in program.yml as a cross-repo enabler.

## Review outcome

Codex IMPL = **LGTM, no BLOCKER/SHOULD-FIX**. Scope parity confirmed (`_under_any(m,
("src/codas",))` ≡ old `_PRODUCT_PREFIX` incl the package-ancestry climb); §11 clean (app →
config.loader, leaf, no cycle); prefix-boundary safe; determinism preserved; all build_atlas_*
consumers (views/calibrate/cli) get the config scope automatically. Two NITs: (1) added a
`# keep in sync with .codas/config.yml` comment by `CODAS_ROOTS` in test_book.py; (2) the
`_PRODUCT_ROOTS_DEFAULT == ("src",)` pin is left as a deliberate contract test.
