# P5 D3b deterministic generated wiki section (governance overview)

## Goal

Second slice of the P5 D3 wiki spine: a **deterministically generated, committed**
Atlas page rendered from repository facts (no LLM), embedding a `source_inventory_hash`
+ a machine-readable `atlas:claims` block. This is the readable "governance map"
rendering of the live facts (the `--emit-pack` pack, D3a, is the agent/tool grounding
feed; this is the committed human/agent page). Foundation for D3d
(`generated_wiki_drift` verifies these pages' claims + freshness).

Authority: `06-19-wiki-architecture` design §0 (governance panels over a static code
dump), §3 link ③ (generated pages must embed `source_inventory_hash` + a nonempty
`atlas:claims` block), §5 generated sections (committed, idempotent), §8 D3b.

## Scope (D3b — one low-churn governance page + the write machinery)

One generated page `.codas/wiki/generated/governance.md` with two **stable**,
high-governance-value panels — intended structure + plan progress:

- **## Structure Units** — table `{unit, path, kind, owner}` from `inventory["units"]`
  (the intended ownership map; §0 panel 1 "intended structure").
- **## Roadmap** — table `{work item, phase, status}` from `inventory["program"]`
  (§0 panel 2 "plan progress").
- a fenced **```atlas:claims```** block: `source_inventory_hash` + verifiable claim
  lines (`unit: <id> -> <path>`, `roadmap: <id> -> <status>`).

Deliberately **excludes** the full symbol index + per-edge dependency graph from the
*committed* page: those are granular/high-churn and already live in the non-committed
`--emit-pack` pack for agents/tools. The committed page is the stable governance map
(design §0 explicitly de-weights a "static code dump"). More panels/pages are a trivial
extension.

Machinery:
- `app/wiki.py`: `render_generated_overview(inventory, source_inventory_hash) -> str`
  (pure markdown); `write_generated_sections(repo) -> list[Path]` (builds the
  generated-excluded inventory, computes the hash, renders, writes the file).
- `cli.py`: `codas wiki --write` → writes the page(s), prints what was written.
- The generated page is **committed** (gitignored files are dropped by
  `--exclude-standard` and would never be checked by D3d).

`--verify` and the `generated_wiki_drift` policy are D3c/D3d (the page is committed but
unguarded until then — acceptable incremental delivery; regenerate at D3d).

## Dogfood-cleanliness (must hold)

The committed page must keep `codas check .` = 0. Engineered from the wiki-parser facts
(`adapters/wiki.py`):
- **Neutral headings** (`## Structure Units`, `## Roadmap`) — NOT the parser's
  claim-creating headings (`canonical sources`/`concepts`/`required synchronization`)
  and no `Evidence:` label → the page creates **no** `wiki_claims` (so no
  `stale_wiki_claim` noise).
- **`atlas:claims` in a fence** — the wiki adapter is fence-aware (skips fenced
  content) → the block creates no claims; D3d ships its own parser.
- **Real paths only** (inventory-derived) → even if `doc_claims`/`stale_claim` see a
  code-span path, it exists. No markdown links to non-existent paths.
- Page lives under `.codas/wiki` → owned by the `atlas-wiki` unit (no `missing_owner`).

## Determinism / idempotency (must hold)

- Render is a pure function of the inventory + hash; tables + atlas:claims sorted on
  total keys; no timestamp.
- `source_inventory_hash` excludes `.codas/wiki/generated/` (D3a's `exclude_under`), so
  writing/regenerating the page does **not** move the hash it embeds — `--write` twice
  is byte-identical (idempotent). The hash moves only when source facts move.
- `codas inventory --json` stays byte-identical across processes with the page present.

## Acceptance Criteria

- [ ] `codas wiki --write` writes `.codas/wiki/generated/governance.md` with the two
      panels + a fenced `atlas:claims` block containing `source_inventory_hash` and
      `unit:`/`roadmap:` claim lines.
- [ ] `render_generated_overview` is pure + deterministic (two calls equal, input
      unmutated).
- [ ] `--write` is idempotent: running twice leaves the file byte-identical.
- [ ] The committed page → `codas check .` = 0 (no `stale_wiki_claim`/`stale_claim`/
      `missing_owner`/`spec_drift` finding); proven on the real repo.
- [ ] `inventory --json` byte-identical across two processes with the page committed.
- [ ] The page creates **zero** `wiki_claims` (asserted via `extract_wiki_claims`).
- [ ] Full unittest suite green.

## Notes

- The `atlas:claims` schema (`source_inventory_hash` + `unit:`/`roadmap:` lines) is the
  contract D3d's parser consumes — keep it simple + line-oriented.
- Churn is intentional for a live governance map, but kept low by scoping the committed
  page to stable facts (units/roadmap), not per-symbol/per-edge data.
