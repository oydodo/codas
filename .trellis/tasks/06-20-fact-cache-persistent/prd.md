# Persistent content-hash fact cache (fact-cache slice 2)

## Status

**DEFERRED (2026-06-20) — co-design with `spec-drift-fact-delta` v2.** Follow-up to
`06-19-incremental-fact-cache` (Slice 1, shipped: single parse pass +
`build_inventory`↔`ScanContext` unify). This task adds the **cross-run** win — a
content-addressed persistent cache so a second run on an unchanged tree re-parses **0**
files — and the cheap `inventory@HEAD` substrate `spec-drift-fact-delta` (v2) needs.

Codex design review recommended deferring: the cache's only consumer beyond raw speed
is v2's `inventory@HEAD`, the speed win is milliseconds on this repo, and the Layer-2
resolver rewrite is byte-identical risk without proportional payoff. v2 will be built
first (it can compute the HEAD-vs-now fact-delta directly, without the cache); its exact
fact needs then FREEZE the `RawFileFacts` schema before the cache commits to it. See
`design.md` for the schema gaps codex found (import `kind`/`asname`, `call_scopes`
materialization, the read-error state) and the `.codas/cache/` gitignore precondition
(fixed preemptively).

## The insight (from Slice 1's PRD)

A file's facts are a **pure function of its content**: `facts(file) = f(bytes(file))`.
Cross-file *resolution* (import `target_path`, call edges, first-party membership)
depends on the file SET but is cheap relative to parsing. So split:

- **Layer 1 — per-file RAW facts (EXPENSIVE → cached):** parse one file once, emit its
  own facts as written (def names+lines, import statements, call sites + lexical
  scope). Keyed by **content hash (git blob SHA where available)**. JSON-serializable.
- **Layer 2 — cross-file resolution (CHEAP → recomputed every run):** resolve raw
  facts against the current file set (import `target_path`, call edges to defs,
  first-party membership). Pure dict lookups, no I/O, no re-parse.

A change to file B updates unchanged file A's *resolved* facts (A's bytes unchanged →
Layer 1 cache hit, but Layer 2 re-runs) — cross-file correctness never depends on the
cache.

## Determinism guard (load-bearing — this killed pyan)

- Cached output is **byte-identical** to a full scan (same blob SHA → same raw facts →
  same resolution → same inventory hash).
- A `--no-cache` full path always exists; a test **cross-checks** cached == full on
  this repo + mixed dirty/clean fixtures.
- Corrupt/missing/partial cache degrades gracefully to a full scan; correctness
  unaffected. The cache is an **optimization, never a source of truth**.
- `inventory --json` stays reproducible across processes with the cache **on and off**.
- Cache lives in a **gitignored** `.codas/cache/` (hash → raw-facts JSON). Never
  committed (avoids inventory churn + the D3 self-reference concern).

## Acceptance criteria (draft)

- [ ] Per-file raw facts (symbols/imports/calls) cached by content hash in gitignored
      `.codas/cache/`; second run on an unchanged tree parses **0** files (probe).
- [ ] Editing N files re-parses exactly those N (parse-counter fixture).
- [ ] `--no-cache` path exists; test asserts cached == full-scan output (byte-identical)
      on this repo + mixed dirty/clean fixtures.
- [ ] `inventory --json` byte-identical across processes, cache on and off.
- [ ] Corrupt/missing cache entry → silent graceful full scan for that file.
- [ ] Full suite green; `codas check .` = 0; inventory byte-identical; `wiki --verify`
      clean. §11/§17 clean (cache lives under `codas.adapters`/a cache module, never in
      a policy; no LLM).
- [ ] `.codas/cache/` gitignored.

## Out of scope (deferred)

- Daemon / filesystem-watch warm process (stateful, CI-unfriendly).
- Parallel/multiprocess parsing (orthogonal).
- The `inventory@HEAD` fact-delta consumer itself — that is `spec-drift-fact-delta`
  (this task only makes it cheap by caching HEAD's blobs).

## Notes

- The Slice-1 `(repo, files)` wrappers + `parse_python_modules` are the designed cache
  seam. The work here is splitting each `*_from_parsed` into a per-file RAW stage
  (cacheable, serializable) + a cross-file RESOLVE stage, then keying the raw stage by
  blob SHA. See `design.md` for the raw-fact schema + the cache contract.
