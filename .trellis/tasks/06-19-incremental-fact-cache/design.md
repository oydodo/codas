# Design — content-addressed incremental fact cache

## Slice decomposition (bounded, each determinism-verifiable)

The PRD's full vision splits cleanly into two slices with a hard determinism guard at
each. Implement **Slice 1 first** (the safe intra-run win + the architectural enabler);
**Slice 2** adds cross-run persistence and is what `spec-drift-fact-delta` (v2) needs for
a cheap `inventory@HEAD` vs `inventory@now` fact-diff.

### Slice 1 — single-parse-pass + unify the scan (no persistent cache)

Kills the intra-run redundancy: today `extract_symbol_facts`, `extract_import_facts`,
and `extract_call_facts` EACH re-read + `ast.parse` every `.py` (3× parse), and
`check --json` additionally runs `build_inventory` in parallel to the `ScanContext` scan
(double scan). This slice introduces ONE parse per file per run and ONE shared scan.

- **`adapters/python_parse.py` (new): `parse_python_modules(repo, files) ->
  ParsedModules`** — read + `ast.parse` each `.py` exactly once; return `{rel: tree}` +
  `skipped`. Pure, deterministic, no resolution.
- Refactor the three Python extractors to accept pre-parsed trees instead of re-reading:
  `extract_symbol_facts(parsed)`, `extract_import_facts(parsed)`,
  `extract_call_facts(parsed)`. Their OUTPUT is unchanged (byte-identical facts) — only
  the parse is shared. Keep the old `(repo, files)` signatures as thin wrappers that call
  `parse_python_modules` then delegate, so nothing else breaks during the transition.
- **`ScanContext`** gains a memoized `_parsed()` (calls `parse_python_modules` once);
  `symbols()/imports()/calls()` consume it. One parse per run.
- **Unify `build_inventory` ↔ `ScanContext` (folds the standing P3-S1 backlog):**
  `build_inventory(repo)` builds (or accepts) a `ScanContext` and PROJECTS it into the
  inventory dict, instead of re-running `discover_files` + every `extract_*`. Then
  `check` (which already has a `ScanContext`) and `check --json` (which calls
  `build_inventory` for provenance) share ONE scan.
  - Care: `build_inventory` currently takes `exclude_under` (for the wiki pack). Thread
    it so the pack's generated-excluded inventory still works (a `ScanContext` built over
    the filtered file set, or an inventory projection that filters). Keep the
    byte-identical inventory + the pack's `source_inventory_hash` semantics intact.
- **Determinism guard:** the inventory JSON + all fact outputs are byte-identical before
  and after (a test asserts `build_inventory(repo)` unchanged; the existing
  byte-identical + 265-test suite is the regression net). No behavior change — pure
  dedup of work.

### Slice 2 — content-hash persistent cache (the cross-run win)

- **Layer 1 (cached):** `parse_python_modules` → per-file RAW facts (defs, import
  statements as written, call sites) keyed by **git blob SHA** (`git ls-files -s` for
  tracked; hash the dirty few directly — `changed_paths` already enumerates them). Cache
  = gitignored `.codas/cache/<hash>.json`. Cache hit → skip parse.
- **Layer 2 (always recomputed):** cross-file resolution (import `target_path`, call
  edges, first-party membership) over the union of Layer-1 facts — pure dict lookups, no
  I/O. So a change to file B correctly updates unchanged file A's resolved facts;
  cross-file correctness never depends on the cache.
- **Determinism guard (load-bearing):** cached output is byte-identical to a full scan
  (same blob SHA → same raw facts → same resolution). A `--no-cache` full path always
  exists; a test cross-checks cached == full on this repo + mixed dirty/clean fixtures.
  Corrupt/missing cache → graceful full scan. `.codas/cache/` gitignored (never a truth
  source; avoids inventory churn + the D3 self-reference concern).
- This is what `spec-drift-fact-delta` (v2) consumes: `inventory@HEAD` is cheap because
  HEAD's blobs are already cached → the fact-delta (symbols/imports/calls added/removed)
  is nearly free.

## Scope of THIS task

**Slice 1 only.** It is bounded, determinism-safe (no behavior change), and delivers the
architectural unify (P3-S1) + the single-parse win that every command benefits from.
Slice 2 (the persistent cache) is a follow-up task (it carries the real cache complexity
+ the cross-run/spec-drift-v2 payoff and deserves its own rhythm pass). Update the PRD
title/scope note accordingly.

## Slice 1 — concrete steps

1. `adapters/python_parse.py`: `parse_python_modules(repo, files) -> ParsedModules`
   (`{rel: ast.Module}` + `skipped`; sorted, deterministic).
2. Refactor `adapters/python.py` (`extract_symbol_facts`, `extract_import_facts`) +
   `adapters/callgraph.py` (`extract_call_facts`) to a `*_from_parsed(parsed)` core +
   keep the `(repo, files)` wrapper. NB callgraph's `_parse_modules` already builds a
   parsed structure — refactor it to consume `parse_python_modules`' trees so it doesn't
   re-parse.
3. `facts/context.py`: `ScanContext._parsed()` memoized; `symbols()/imports()/calls()`
   use it. (Markdown/wiki/trellis/git adapters are out of scope for the parse-share —
   they don't `ast.parse`; the single-parse-pass is Python-only. They still benefit from
   Slice 2's content-hash cache.)
4. `structure/inventory.py` + `app/inventory.py`: `build_inventory` projects from a
   `ScanContext` (built once), not its own `discover_files`/`extract_*`. Preserve
   `exclude_under`. `run_inventory`/provenance unchanged externally.
5. `app/check.py` / `app/provenance.py`: `check --json` reuses the run's `ScanContext`
   for provenance instead of a second `build_inventory` scan (or build_inventory accepts
   the existing ctx). One scan per `check --json`.
6. Tests: parse-count probe (each `.py` parsed once per run — instrument
   `parse_python_modules` call count via monkeypatch); `build_inventory` byte-identical
   before/after; `inventory --json` byte-identical across processes; full suite + check 0.

## Determinism / dogfood

- No fact output changes → inventory byte-identical, 265 tests green, check 0. The
  refactor is pure work-deduplication.
- §11 holds: the parse helper lives in `codas.adapters` (Python ecosystem); policies
  still consume via `ScanContext`. `build_inventory` (in `codas.structure`) consuming a
  `ScanContext` is the existing inventory↔facts bridge (allowed; structure-module is the
  bridge, not a policy).
- New names unique (`parse_python_modules`, `ParsedModules`, `*_from_parsed`).

## Open questions for review

1. Slice 1-only scope for this task (cache = follow-up) — agree, or do both here?
2. `build_inventory` consuming a `ScanContext`: cleanest seam for `exclude_under` (build
   the ctx over a filtered file set vs filter at projection)? The pack needs the
   generated-excluded inventory + its narrowed source_inventory_hash unchanged.
3. Keep the `(repo, files)` adapter wrappers (back-compat during transition) vs migrate
   all call sites to `*_from_parsed` now? Leaning: keep wrappers (smaller diff, the
   wrappers are the cache seam in Slice 2 anyway).
4. ParsedModules holding live `ast` trees in memory for the whole run — fine for this
   repo; for a 10k-file repo Slice 2's cache stores raw FACTS (json), not trees, so memory
   is bounded there. Acceptable for Slice 1.
