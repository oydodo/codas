# Design — persistent content-hash fact cache (Slice 2)

## RE-EVALUATED (2026-06-21): BENCHMARK SAYS STAY DEFERRED — do not build now

Picked up to BUILD (the 2026-06-20 defer-condition — "co-design with v2" — is mechanically
LIFTED: v2 substrate shipped in `06-20-fact-delta-substrate` `54968e8`, the `RawFileFacts`
schema froze). Ran a fresh codex DESIGN re-review (APPROVE-WITH-CONSTRAINTS) + a benchmark.
**The benchmark disqualifies the build on payoff.**

**Benchmark (this repo, 145 `.py` of 421 scanned, min-of-N):**

| stage | cost | cacheable? |
|---|---|---|
| parse (`parse_python_modules`, the Layer-1 work) | **74 ms** | yes — but only warm + file UNCHANGED |
| resolution (the 3 `*_from_parsed` extractors = Layer 2) | **151 ms** | NO — cross-file, recomputed every run |
| `build_inventory` total | 283 ms | — |

- The design ASSUMED "resolution is cheap relative to parsing." The data is the OPPOSITE:
  **resolution is 2× the parse**, and resolution is the part the cache CANNOT remove.
- Cache ceiling = the 74 ms parse = **26 % of inventory**, warm-and-unchanged only. codex's
  stated precondition ("build only if parse DOMINATES") is FALSE — resolution dominates 2:1.
- The byte-identical RISK is the callgraph descriptor rewrite (the `_bindings` ast.walk
  last-write order, `call_scopes` materialization, read-error re-raise). High risk for a
  26 % warm-only win on the cheaper half. Not worth it.

**The invocation model seals it (why frequency never reaches save-rate).** Codas is a GATE,
not a watcher (`integrations/enforcement.py`): it installs `pre-commit` + `pre-push` hooks
(`exec codas check .`, block on error findings) + a CI workflow (check on push/PR). The
agent loop is: `codas preflight --task <id>` BEFORE editing (on demand) → `codas impact` /
`codas query` DURING (on demand, targeted) → `codas check` AT commit/push/CI (whole-tree
gate). NONE of those is per-save. At a handful of gate runs per session, a 74 ms parse
saving is invisible. The cache only ever mattered at save-frequency, which the design
deliberately does not use.

**DECISION: keep DEFERRED (status → planning).** Not "never" — a permission structure.

**RE-EVALUATE TRIGGER (any one):** a real LARGE Python repo (≈3000+ `.py`) profile showing
parse time DOMINATES whole-tree `codas check` (multi-second, parse the majority); OR a
demonstrated save-frequency invocation need (which the gate model would have to adopt first).
Until then the gate model has no cache-shaped gap.

If ever built, the codex APPROVE-WITH-CONSTRAINTS holds — must-hold: raw import descriptors
in EXACT `ast.walk` order (no sort before `_bindings` replays them, last-write-wins); call
scope + call-site traversal order preserved (params + Store locals + caller class/symbol/line
+ only Name/Attribute(Name) call shapes); RawFileFacts/cache-read-path carries read-error vs
parse-error and RE-RAISES read errors for in-scope package files (FactSnapshot does NOT carry
this); single raw-byte read for both key and decoded parse input, direct hash = `sha1(b"blob
<len>\0" + raw_bytes)` (verified to match `git hash-object` exactly); cached-vs-`--no-cache`
+ raw-vs-parsed equivalence tests before enabling; preserve the W7 `ScanContext`
additions (`_derived_prefixes`, `derived_output_prefixes` threading, `head_snapshot` 3rd
param) when reattaching `._parsed()` → `._raw()`.

---

## DECISION (2026-06-20): DEFERRED — co-design with spec-drift-fact-delta v2

Codex design review verdict: **defer Slice 2 as currently designed; co-design the
cache read-path WITH `spec-drift-fact-delta` v2** (the cache's only consumer beyond raw
speed is a cheap `inventory@HEAD`; on this repo the speed win is milliseconds, so the
Layer-2 resolver rewrite is byte-identical risk without proportional payoff). v2 can
compute its HEAD-vs-now fact-delta WITHOUT the persistent cache (recompute both
inventories directly — correct, just slower); building v2 first lets its exact fact
needs FREEZE the `RawFileFacts` schema before the cache commits to it. This task stays
in PLANNING until v2 is underway.

## SCHEMA FROZEN (2026-06-20): spec-drift v2-A substrate shipped

`06-20-fact-delta-substrate` (commit `54968e8`) shipped the HEAD fact snapshot v2
needed, WITHOUT the persistent cache — it recomputes the HEAD snapshot directly via
`git ls-tree`/`cat-file` (correct, slower; the cache is now a pure optimization). It
froze the schema this cache will store:

- The cached per-file unit is the **per-file slice of `codas.facts.snapshot.FactSnapshot`**
  (`{symbols, imports, calls}`). Layer-1 `RawFileFacts` = one file's contribution to that
  snapshot BEFORE cross-file resolution; Layer-2 `assemble_*` = `extract_*_from_parsed`
  over the union (the resolution logic already split this way for snapshots).
- **Package detection is already file-set-derived** (v2-A moved callgraph off the
  filesystem stat onto `package_dirs_of`, gated on `read_error is None`). So Layer-2's
  package math is `package_dirs_of(union-of-readable-paths)` — no remaining working-tree
  filesystem dependency to design around. This resolves the design's "RawFileFacts needs
  a read-error state" gap: the snapshot/`ParsedModule` already carry it, and package
  membership already excludes read-error files.
- **Decode is pinned**: working-tree + HEAD both `read_bytes().decode("utf-8","ignore")`,
  so the cache key (git blob sha) and the parse input are over the same bytes (the
  design's "key/parse-input consistency" requirement is satisfied upstream).
- The import-descriptor `kind`+`asname` and `call_scopes` materialization gaps from the
  schema-gaps list below still apply to the Layer-1 RAW serialization (the snapshot keeps
  live `ast`-derived facts, not yet a serialized descriptor) — these remain the cache's
  work.

**Schema gaps codex found (must fix before any Layer-2 rewrite ships):**
- **Import descriptor needs `kind` + `asname`.** `_bindings` (callgraph) reads
  `alias.asname` (so `import pkg.mod as m; m.f()` binds `m`; `from p import f as g; g()`
  binds `g`) and must distinguish `ast.Import` vs `ast.ImportFrom`; `_targets` (python)
  emits the `from`-base only when `module is not None` and filters first-party
  submodules — both need the explicit `kind`. So the raw import descriptor is
  `{kind: "import"|"importfrom", module, level, names: [{name, asname}], lineno}`.
- **`call_scopes` must be materialized at RAW-extraction time with the no-nested-scope
  walk already applied** (`_walk_no_nested` skips child def/class) and traversal order
  preserved EXACTLY (`module.tree.body` then each `class.body`) — the first-edge-wins
  dedup depends on it. `locals` must include params (posonly/args/kwonly/vararg/kwarg)
  AND Store-names, not Store-only.
- **`RawFileFacts` needs a read-error/parse-error state** parallel to Slice-1's
  `ParsedModule.read_error` (callgraph re-raises read_error for in-scope package files;
  symbols/imports skip `tree is None`) — the cache must carry it or route errors outside
  the cache path.
- `_resolve_call` + dedup/sort are descriptor-safe as designed (confirmed).

**Independent latent bug fixed NOW (not gated on the cache): `.codas/cache/`
gitignore.** `discover_files` uses `git ls-files --others --exclude-standard`; if
`.codas/cache/` is not ignored before the first cache write, cache JSON enters the
inventory as unowned artifacts and shifts `source_inventory_hash`. Added to `.gitignore`
preemptively this commit so the precondition can never be forgotten.

**Cache implementation notes folded for when it ships:** decode+parse from the EXACT
bytes used to compute the blob-SHA key in ONE read (no hash-bytes-A / parse-bytes-B
desync); atomic temp-file+rename cache writes; `scan_raw_facts` must consume the
already-filtered `ctx.files` (never rediscover) so `exclude_under` / the pack's
`source_inventory_hash` stay correct.

The original design follows (kept as the starting point for the co-design pass).

---


## What Slice 1 already gave us (the seam)

`parse_python_modules(repo, files) -> ParsedModules` is the single parse pass, and the
three extractors are `*_from_parsed(parsed)` cores behind `(repo, files)` wrappers.
But `ParsedModules` holds live `ast.Module` trees — **not serializable**. Slice 2
caches **facts, not trees**, so the cache seam sits one layer below the trees: a
per-file RAW-fact stage (a pure function of the file's bytes, JSON-serializable) plus a
cross-file RESOLVE stage (cheap, always recomputed).

## The two layers

### Layer 1 — per-file RAW facts (cached, keyed by content hash)

For one file's `ast.Module`, emit everything derivable from THAT file alone, with NO
cross-file lookup. JSON-serializable. This is the unit the cache stores.

```
RawFileFacts = {
  "symbols":     [[name, kind, line], ...],          # top-level class/func defs
  "imports":     [{module, level, names:[...], lineno}, ...],   # every Import/ImportFrom (ast.walk order)
  "defs":        {name: line, ...},                  # callgraph: top-level func/class -> line
  "classes":     {cls: {method: line, ...}, ...},    # callgraph: class -> methods
  "call_scopes": [                                   # callgraph: one per caller scope, walk order
     {caller_class, caller_symbol, caller_line,
      locals: [sorted names],
      calls: [ {func_kind:"name", id}                # foo()
             | {func_kind:"attr", base, attr} ] }    # base.attr() incl. self.m()
  ],
}
```

Notes:
- `symbols` is already resolution-free (the `module` field is the file path, attached
  at assembly time, not stored).
- `imports` stores the import STATEMENTS as written (module/level/names/lineno). The
  absolute-dotted resolution, `target_path`, and `from pkg import submodule` filtering
  are cross-file → Layer 2.
- `defs`/`classes`/`call_scopes` are exactly what `_modules_from_parsed` +
  `_module_edges` read, minus the cross-file `by_name`/`bindings`. `call_scopes`
  captures only the resolvable call shapes (`ast.Name` func, `ast.Attribute` on a
  `ast.Name` — which covers `self.m()`); other shapes resolve to nothing today and are
  dropped at extraction, so they need not be cached. The call site's own line is NOT
  needed (a `CallFact`'s lines are the caller-scope def line + callee def line).

### Layer 2 — cross-file resolution (always recomputed, no I/O)

Over the union of Layer-1 raw facts for the **current** file set:
- `package_dirs` / `module_paths` (which scanned dirs are packages; dotted→path) — pure
  path math over the file set (already in `extract_import_facts_from_parsed`).
- imports: rewrite `_targets`/`_resolve_import` to consume a raw import descriptor
  `{module, level, names}` instead of an `ast` node; emit `ImportFact` with
  `target_path` via `module_paths`.
- calls: rebuild a lightweight module view from `defs`/`classes`/`imports` (no
  `ast.Module`), then run the EXISTING `_bindings` / `_module_edges` / `_resolve_call`
  logic — rewritten to read `call_scopes` descriptors + raw import descriptors instead
  of `ast` nodes. The resolution LOGIC is unchanged (1:1 field mapping); only its input
  type changes. `_module_name` (filesystem package check) still computes scope/dotted.

The Layer-2 rewrite is the **byte-identical risk surface**. The guard: a test asserts
`*_from_raw(...)` == the Slice-1 `*_from_parsed(...)` on every existing fixture (the
golden outputs already pinned by the 271-test suite) + the cached==full cross-check.

## The cache

- **Module:** `codas/adapters/fact_cache.py` (an adapter-layer concern; policies never
  touch it — §11). Pure functions + a small `FactCache` over `.codas/cache/`.
- **Key = content hash, git blob SHA where available.** `git ls-files -s <root>` gives
  `<mode> <blobsha> <stage>\t<path>` for tracked files in one call → `path -> blobsha`
  (no rehash). Dirty/untracked files (`changed_paths` already enumerates them, or any
  path absent from `ls-files -s`): hash the bytes directly with the SAME algorithm git
  uses (`sha1("blob %d\0" % len + data)`) so a staged-then-edited file and its blob
  never collide and the key is identical whether or not git knows the content yet.
- **Storage:** `.codas/cache/<blobsha>.json` = the `RawFileFacts` for that content.
  Content-addressed ⇒ **automatic invalidation** (content changes → new sha → miss). No
  manual invalidation logic.
- **Read path (`parse_python_modules` replacement / wrapper):** for each `.py`, resolve
  its key; cache hit → load `RawFileFacts` (no parse); miss → parse once, extract
  `RawFileFacts`, write `.codas/cache/<sha>.json`, use it. A read/JSON/parse error on a
  cache file → treat as miss (parse fresh); never trust a malformed entry.
- **`--no-cache`:** a flag threaded to the scan that bypasses read+write entirely
  (always parse). The determinism cross-check runs cached vs `--no-cache`.

### Where the seam attaches

Introduce `raw_file_facts(tree) -> RawFileFacts` (pure, per tree) and
`assemble_*(raw_by_path, repo) -> SymbolFacts|ImportFacts|CallFacts` (Layer 2). Then:
- `parse_python_modules` stays for the `--no-cache` / non-cached path.
- A new `scan_raw_facts(repo, files, *, cache) -> dict[path, RawFileFacts]` does the
  cache-or-parse loop and is what `ScanContext` calls. `ScanContext._parsed()` becomes
  `ScanContext._raw()` (memoized `dict[path, RawFileFacts]`); `symbols/imports/calls`
  call the `assemble_*` Layer-2 functions over it.
- The Slice-1 `extract_*_from_parsed(parsed)` either (a) stays as a thin shim that
  derives `RawFileFacts` from the trees then assembles (keeps the parse-once path), or
  (b) is superseded by `raw_file_facts` + `assemble_*`. Keep `(repo, files)` wrappers.

## Determinism / dogfood (load-bearing)

- **Cached == full, byte-identical.** A test cross-checks `inventory --json` (and each
  fact tuple) with cache ON vs `--no-cache` on this repo + mixed dirty/clean fixtures.
- **Equivalence to Slice 1:** `assemble_*` over `raw_file_facts(tree)` must equal
  Slice-1 `extract_*_from_parsed(parsed)` on every fixture (the existing suite is the
  golden net). Add a direct assertion.
- Corrupt/missing/partial cache entry → graceful per-file full parse (test with a
  truncated `.json`).
- `.codas/cache/` gitignored; cache facts NEVER enter the inventory (the inventory is
  the resolved projection, identical with cache on/off). No timestamps, stable sort.
- §17 (no LLM), §11 (cache under `codas.adapters`, consumed via `ScanContext`; policies
  untouched). New names unique (`fact_cache`, `raw_file_facts`, `RawFileFacts`,
  `scan_raw_facts`, `assemble_symbols/imports/calls`).

## Open questions for review (codex design pass)

1. **Sequencing / value:** the cache's only consumer beyond raw speed is
   `spec-drift-fact-delta` v2 (cheap `inventory@HEAD`). On a repo this size the cache
   saves milliseconds. Is the Layer-2 descriptor rewrite (real byte-identical risk)
   worth shipping NOW, or should Slice 2 be **co-designed with v2** (which needs the
   HEAD-vs-now fact-diff anyway)? Recommend a call; default leaning = build the cache
   now (it is well-bounded by the cached==full cross-check) but keep the Layer-2 rewrite
   behind the equivalence test so it cannot silently drift.
2. **Call-site serialization completeness:** does `call_scopes` capture every field the
   existing `_resolve_call`/`_local_names`/`_walk_scope` read (locals incl. params +
   stored names; no nested-scope descent; `self.` handling)? Any `ast` detail that does
   not survive the descriptor round-trip is a byte-identical bug — enumerate them.
3. **Blob-SHA vs direct hash parity:** confirm the direct-hash path reproduces git's
   blob sha exactly (`blob <len>\0<bytes>`, the raw bytes — mind the Slice-1
   `read_text(errors="ignore")` decode: the cache key must be over the BYTES git
   hashes, while the parse uses the decoded text; keep key and parse-input consistent so
   a non-UTF8 file can't desync key vs facts).
4. **`exclude_under` / file-set interactions:** Layer 2 resolves over the CURRENT file
   set, so `exclude_under` (wiki pack) still pre-filters the set before assembly — the
   cache is per-file and set-independent, so excluding a file just drops it from the
   union. Confirm no `source_inventory_hash` interaction.
5. **Cache dir creation + concurrency:** first run creates `.codas/cache/`; concurrent
   runs writing the same `<sha>.json` — atomic write (temp + rename) needed?
