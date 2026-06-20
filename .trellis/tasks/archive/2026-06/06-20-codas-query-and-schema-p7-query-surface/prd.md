# codas query + codas schema — P7 jq-optional query surface

## Status

PLANNING — P7 deliverable 1, second slice after `codas impact`. Completes the "thin set
of query subcommands so jq is optional" from program.yml P7 + the `codas impact` PRD's
out-of-scope list. CLI-first, MCP-optional (decision 2026-06-20).

## Scope

Two read-only, deterministic subcommands over the existing inventory facts — ZERO new
extraction, pure projection/filter:

- **`codas query <kind> [--select FIELD=VALUE]... [--repo]`** — emit the rows of one
  inventory fact block as deterministic JSON, optionally filtered by field equality
  (repeatable `--select`, AND-combined; string compare so `--select line=10` works). A
  pre-shaped slice so an agent need not pipe `codas inventory --json | jq`.
  - kinds → (inventory block, row subkey): `symbols`→symbols.definitions,
    `imports`→imports.edges, `calls`→calls.edges, `units`→units (the block IS the list),
    `tasks`→tasks.items, `doc-claims`→doc_claims.references,
    `html-claims`→html_claims.references, `wiki-claims`→wiki_claims.claims,
    `work-items`→program.work_items.
  - Deterministic: the inventory is already sorted; filter preserves order. Unknown kind →
    a clean error listing valid kinds (exit 2). Unknown `--select` field → empty result
    (not an error; the field simply matches nothing) — documented.
- **`codas schema [--repo]`** — emit, per kind, the row field names DERIVED from the live
  inventory (sorted union of keys across that block's rows) + the backing block/subkey.
  The JSON shape contract so an agent need not reverse-engineer it. Derived from inventory
  (NOT hand-authored) so it cannot drift from the real shape — a populated repo (this one)
  yields the complete field set.

## Out of scope

- `--field` projection (return only some columns) — sugar on sugar; add later if needed.
- MCP shell, role integrations, OSS LLM-wiki adapters (other P7 deliverables).
- Any new fact — query/schema are pure projections of `codas inventory`.

## Acceptance

- [ ] `codas query symbols --select module=...` returns the matching definition rows as
      deterministic JSON, byte-identical across runs; `codas query calls --select
      caller_symbol=run_impact` works; unknown kind exits 2 with the valid-kind list.
- [ ] `codas schema` lists every populated kind with its field names, deterministic.
- [ ] 0 new inventory facts (read-only); `codas check .` = 0; full suite green;
      §11 clean (app/query.py imports no adapter; projects the inventory).

## Notes

- Mirrors `codas impact` (read-only projection over inventory facts, deterministic JSON).
- Together with `impact` + the existing `--json` on check/inventory/preflight, this is the
  full CLI-first agent-query contract; MCP stays optional.
