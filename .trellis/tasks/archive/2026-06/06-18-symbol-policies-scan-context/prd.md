# PRD — P3 A2: migrate symbol policies to ScanContext

## Context

P3 §11 Adapter Boundary. A1 introduced `ScanContext` (`codas.facts.context`) and
migrated `stale_claim` off its direct adapter import. Two policies still violate
the boundary:

- `src/codas/policies/duplicate_symbol.py:6` — `from codas.adapters.python import SymbolFact, extract_symbol_facts`
- `src/codas/policies/duplicate_implementation.py:6` — same Python import

Both also re-run `discover_files` + `extract_symbol_facts` themselves (the scan
runs twice for symbols across one `codas check`).

## Goal

Add a `symbols()` accessor to `ScanContext` and migrate both policies to consume
it, removing their `codas.adapters.python` and `codas.structure.index` imports.
After this slice, **no module under `src/codas/policies/` imports `codas.adapters`**.

## Requirements

1. `ScanContext.symbols() -> SymbolFacts` — memoized `extract_symbol_facts` over
   the cached `files`. Emits **all** definitions; each policy keeps its own filter
   (duplicate_symbol: public + `src/`; duplicate_implementation: public+private +
   `src/`).
2. The normalized symbol fact types (`SymbolFact`, `SymbolFacts`) are reachable
   from the facts seam so policies can annotate without importing the adapter.
3. `check_duplicate_symbol(ctx)` / `check_duplicate_implementation(ctx)` — drop
   adapter + `codas.structure.index` imports; read `ctx.symbols()`.
   `duplicate_implementation` keeps its `.codas/claims.yml` loading (facts-only
   provider never absorbs claim loading) via `ctx.repo`.
4. `run_check` threads the existing single `ScanContext` to both.

## Acceptance criteria

- No `src/codas/policies/*.py` imports `codas.adapters` (generalized guard).
- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings".
- `codas inventory . --json` byte-identical across two runs.
- Full suite green (call sites migrated for both symbol-policy test files).

## Non-goals

- Relocating the fact dataclasses (`DocClaim`/`SymbolFact`) out of `adapters/`
  into a neutral `codas.facts` types module — possible later cleanup; A2 surfaces
  the types through the seam only.
- Python import/package facts — B1.
- The dependency-direction enforcement *policy* + `structure.yml`
  `must_not_depend_on: [codas-adapters]` rule — B2 (A2 ships only the test guard).
- Migrating the remaining file-scanning policies (missing_owner, structure_drift,
  …) onto `ScanContext` — they import `codas.structure.index`, not an adapter, so
  they are not a boundary violation; out of scope.
