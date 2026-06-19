# Content-addressed incremental fact cache (scan architecture)

## Status

PLANNING / queued. Performance + scan-architecture rework, below the policy layer.
Captured from a 2026-06-19 design discussion. Not yet sequenced into a phase (see
"Phase placement"). Subsumes the standing P3-follow-up backlog item **S1** (unify
`build_inventory` ↔ `ScanContext`).

## Problem

Every `codas` invocation does a **cold full scan** of the working tree — there is no
persistence, so each CLI process rebuilds all facts from zero. Worse, a single run
scans **more than once**:

- `check` builds a `ScanContext`, but each accessor independently re-reads and
  re-parses every `.py`: `symbols()`, `imports()`, `calls()` each run a full `ast`
  pass → the same files are `ast.parse`d ~3×.
- `check --json` (provenance) additionally calls `build_inventory`, which does its
  **own** `discover_files` + every `extract_*` in parallel to the `ScanContext` scan.
- `inventory`, `preflight`, and the future `codas wiki` (D3) each trigger a full scan.

For a small repo this is milliseconds. At 10k+ files a cold scan is tens of seconds,
and the intra-run redundancy multiplies it. This blocks `codas` as a fast pre-commit /
interactive gate on large repos.

## Why scan at all (the purpose, to preserve)

Codas verifies **claims against reality**: claims = structure map, dependency rules,
wiki assertions, program plan; reality = facts about the *current* code (defs, imports,
call edges). The scan turns the current tree into those facts (`inventory`). Facts must
reflect the **current** tree or the gate lies. The requirement is "a current snapshot",
**not** "rebuild from zero every time" — the latter is the naive implementation, not an
inherent need.

## Key insight

A file's facts are a **pure function of its content**: `facts(file) = f(bytes(file))`.
So a file's facts change only when its bytes change. Cross-file *resolution* (does an
import target resolve first-party? does a call resolve to a def?) depends on the set of
files, but is cheap relative to parsing. This licenses an incremental, content-addressed
cache with a strict determinism guard.

## Design (target)

### Two layers (separate the expensive from the cheap)

- **Layer 1 — per-file raw facts (EXPENSIVE → cached):** parse one file once, emit its
  *own* facts as written (def names + lines, import statements, call sites, doc-claim
  spans, wiki-claim spans). Keyed by **content hash**. One parse pass per file produces
  **all** raw fact kinds (kills the current symbols/imports/calls 3×-parse redundancy).
- **Layer 2 — cross-file resolution (CHEAP → recomputed every run):** resolve raw facts
  against the current file set (import `target_path`, call edges to defs, first-party
  membership). Pure dict lookups, no I/O, no re-parse. Recomputed each run so a change
  to file B correctly updates unchanged file A's *resolved* facts (A's bytes didn't
  change, but its resolution did) — cross-file correctness never depends on the cache.

### Cache key = content hash, ideally the git blob SHA

- Git already content-addresses every tracked file (blob SHA). `git ls-files -s` /
  `git ls-tree` expose blob hashes cheaply → reuse them as cache keys (no rehash).
- Working-tree (uncommitted) files: hash directly (only the dirty few; `changed_paths`
  from `spec_drift` already enumerates them).
- Cache lives in a **gitignored** `.codas/cache/` (hash → raw-facts JSON). NOT
  committed (avoids inventory churn + the D3 self-reference problem).

### Automatic invalidation

Content-hash keys mean invalidation is automatic: content changes → hash changes →
cache miss. No manual invalidation logic (the classic cache-bug source) is needed.

### Unify the scan (folds P3-S1)

One scan feeds both `check` (ScanContext) and `inventory` (build_inventory) — the
inventory becomes a projection of the same Layer-1/Layer-2 result the policies consume.
`check --json` stops double-scanning.

## Determinism guard (the load-bearing constraint)

The cache is an **optimization, never a source of truth**. Hard requirements:

- Cached output is **byte-identical** to a full scan (same content hash → same facts).
- A `--no-cache` full-scan path always exists; a test **cross-checks** cached result
  `==` full-scan result on this repo (and on fixtures with mixed dirty/clean files).
- A corrupt/missing cache degrades gracefully to a full scan; correctness unaffected.
- `inventory --json` stays reproducible across processes (the existing byte-identical
  invariant) with the cache on **and** off.

## Out of scope (rejected / deferred)

- **Daemon / filesystem-watch warm process**: fastest for interactive, but stateful,
  CI-unfriendly, staleness-bug-prone → not the default; the cache is simpler and
  sufficient. Could revisit for an IDE/LSP integration later.
- **Committed inventory snapshot**: churns every commit + self-references (D3) →
  gitignored cache instead.
- Parallel/multiprocess parsing (orthogonal; can layer on later).

## Acceptance criteria (draft)

- [ ] One `ast.parse` per file per run (no per-accessor re-parse); all raw fact kinds
      from the single pass.
- [ ] Layer-1 facts cached by content hash (git blob SHA where available) in gitignored
      `.codas/cache/`; second run on an unchanged tree re-parses **0** files.
- [ ] Editing N files re-parses exactly those N (verified by a parse counter / fixture).
- [ ] `build_inventory` and `ScanContext` share one scan; `check --json` scans once.
- [ ] `--no-cache` path exists; test asserts cached == full-scan output (byte-identical)
      on this repo + mixed-state fixtures.
- [ ] `inventory --json` byte-identical across processes, cache on and off.
- [ ] Full suite green; `codas check .` = 0.

## Phase placement (open)

Cross-cutting performance/architecture, not a P5-wiki deliverable. Options: (a) its own
item before D3 (D3's `codas wiki` will scan too, so it benefits); (b) after D3 v0
(correctness-first, optimize when a large repo actually hurts). The discussion leaned
toward capturing it now and deciding sequence vs D3 separately. Subsumes P3-S1; relates
to the codas-next-step backlog. The `changed_paths` substrate from `spec_drift` is a
ready enabler.

## Notes

- Determinism is non-negotiable (it killed pyan earlier). The content-hash key is what
  makes caching safe here — same bytes ⇒ same facts ⇒ identical inventory hash.
- This is the scan-layer analog of the project's recurring discipline: a fast/optional
  mechanism (cache) layered over a deterministic source of truth (full scan), with the
  two cross-checked.
