# PRD — P3 A1: fact-provider / scan-context

## Context

P3 (`program:P3:adapter-extraction`) deliverables are "Swift/XcodeGen checks move
behind adapters" and "Core no longer imports ecosystem concepts" with exit
criterion "Core tests run without Swift/Ciri assumptions". This repo is pure
Python with no Swift/XcodeGen, so P3 is realized by enforcing the §11 Adapter
Boundary in spirit: **core may only receive normalized facts and claims; it must
not import ecosystem-specific adapters.**

Today three policies violate that rule by importing adapters directly:

- `src/codas/policies/stale_claim.py:5` — `from codas.adapters.markdown import extract_doc_claims`
- `src/codas/policies/duplicate_symbol.py:6` — `from codas.adapters.python import SymbolFact, extract_symbol_facts`
- `src/codas/policies/duplicate_implementation.py:6` — same Python import

Each policy also re-runs `discover_files` itself (the recurring "shared scan
context" debt deferred since P2 slice 1): `discover_files` is invoked 5–6× and
`extract_symbol_facts` 2× across a single `codas check` run.

## Goal

Introduce a **fact-provider** seam — `ScanContext` — that runs the file scan and
adapter extraction **once** per run and exposes normalized facts through typed
accessors. Migrate `stale_claim` to consume it, removing that policy's direct
adapter and index imports. This is the A1 proof of the pattern; the other two
policies migrate in A2.

## Requirements

1. New `codas.facts` package with `context.py` defining `ScanContext` (frozen)
   and `build_scan_context(repo, config)`.
2. `ScanContext` is the **only** core-side module permitted to import
   `codas.adapters.*` — the provider seam. Documented explicitly so the boundary
   guard (B2) whitelists it.
3. `ScanContext` exposes `repo`, `config`, `roots`, `files`, and a cached
   `doc_claims()` accessor. The scan (`discover_files`) and `extract_doc_claims`
   each run once and are memoized.
4. `check_stale_claim` signature becomes `check_stale_claim(ctx) -> list[Finding]`;
   it imports no adapter and no `codas.structure.index`.
5. `run_check` builds one `ScanContext` after config load and threads it to
   `check_stale_claim`. The other 11 policy calls are unchanged.

## Acceptance criteria

- `src/codas/policies/stale_claim.py` imports neither `codas.adapters.*` nor
  `codas.structure.index`.
- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings" (0).
- `codas inventory . --json` is byte-identical across two runs and unchanged from
  before this slice (`build_inventory` is untouched).
- Full suite green: `PYTHONPATH=src python3 -m unittest discover -s tests`.
- A unit test proves `stale_claim` no longer imports an adapter (regression guard
  for this file; the general policy→adapter import ban is B2).

## Non-goals (explicit)

- Migrating `duplicate_symbol` / `duplicate_implementation` — A2.
- Python **import/package** facts and the dependency-direction policy — B1/B2.
- The general "no `codas.policies.*` imports `codas.adapters.*`" enforcement
  policy — B2 (only `stale_claim` is provably clean after A1).
- Refactoring `build_inventory` to consume `ScanContext` — P3-later; keeping it
  untouched protects the byte-identical inventory invariant.
- Adding `symbols()` / `tasks()` / `artifact_index()` accessors — added when their
  consumers migrate (A2 / later), not speculatively.
- Claim/config loading staying in `duplicate_implementation` — the provider is
  facts-only, never absorbs claim loading.
