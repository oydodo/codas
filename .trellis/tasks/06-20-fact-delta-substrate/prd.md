# spec-drift v2-A: fact-snapshot + fact-delta substrate (inventory@HEAD)

## Status

PLANNING — the low-risk substrate slice of the deferred `spec-drift-fact-delta` v2
(`06-19-spec-drift-fact-delta`). Ships INDEPENDENTLY of the coupling re-authoring
(v2-B), which is the bulk of the risk and stays deferred until this lands.

## Why this slice exists

v2's thesis (see `06-19-spec-drift-fact-delta` PRD): **materiality is a static property
of an authored COUPLING, not a per-change judgment.** Couplings are expressed over
**fact-deltas** ("a `check_*` symbol was added → policies.yml must change"), which are
always-true by construction and need zero semantic judgment (§17-clean). To detect a
fact-delta, Codas needs the code facts at two points — `HEAD` and the working tree — and
the set difference between them.

That substrate (a) does not exist yet and (b) is the shared dependency of BOTH deferred
items: v2-B's couplings consume the delta, and fact-cache slice 2's only consumer beyond
raw speed is a cheap `inventory@HEAD`. Building the substrate first, computing
`inventory@HEAD` directly via git (correct, slower), lets the **`RawFileFacts`/snapshot
schema FREEZE** before the cache commits to it (the co-design the cache's design.md
calls for).

This slice is deliberately scoped to the substrate + a determinism proof. **No policy
changes, no coupling re-authoring, no `drift_couplings` retirement** — `spec_drift` v1
is untouched. That keeps the byte-identical / dogfood surface tiny.

## Scope (what ships)

1. **A code-fact snapshot at an arbitrary git source.** `FactSnapshot{symbols, imports,
   calls}` — the three code-fact streams already extracted, computed for either the
   working tree (from the existing `ScanContext`) or a git ref (`HEAD`).
   - HEAD path: list `.py` at HEAD (`git ls-tree -r HEAD`), read each blob's content
     (`git cat-file` / `git show`), parse, run the EXISTING `extract_*_from_parsed`
     cores. Filtered to the SAME workspace roots as the working-tree scan.
   - "inventory@HEAD" in the handoff means this code-fact snapshot, NOT the full
     structure/program/documents/tasks inventory (those are config facts diffed
     differently; v2 couplings are over code facts).

2. **A pure fact-delta.** `diff_snapshots(base, head_or_work) -> FactDelta` surfacing
   `symbols_added/removed`, `imports_added/removed`, `calls_added/removed` as sorted
   tuples of stable comparable keys. Pure (no I/O), deterministic, total-ordered.

3. **`ScanContext` accessors** so a future policy stays adapter-free: `head_snapshot()`,
   `working_snapshot()`, `fact_delta()` (working-tree-vs-HEAD), each memoized; `None`
   head snapshot when `HEAD` does not resolve (no commits) → empty delta.

4. **Soundness fix for call facts (the key risk).** `callgraph._module_name` currently
   detects packages by statting the WORKING-TREE filesystem (`(repo/dir/__init__.py)
   .exists()`), so a HEAD snapshot built from HEAD content would mix HEAD content with
   working-tree structure — unsound. `python.py` already derives packages purely from
   the file SET. The call extractor must do the same so the snapshot is a pure function
   of (file-set, content). Design weighs unify-the-refactor (byte-identical-checked) vs
   an opt-in package-set override (zero working-tree-path change); see design.md.

## Out of scope (stays deferred → v2-B / slice 2)

- Coupling schema over fact-deltas; re-authoring `must_update_if_changed` into precise
  fact-level couplings; retiring `drift_couplings`; the `spec_drift` v2 policy rewrite.
- The persistent content-hash cache (slice 2). v2-A recomputes both snapshots directly
  (slower, correct); the cache later makes `inventory@HEAD` cheap. The snapshot schema
  this slice freezes is what the cache will store.
- `--since <ref>` arbitrary range diffs (only working-tree-vs-HEAD here).
- Full `inventory@HEAD` (units/program/documents/tasks at HEAD).

## Acceptance criteria

- [ ] `FactSnapshot` computable for the working tree and for `HEAD`, both a pure function
      of (file-set, content) — no working-tree filesystem stat leaks into the HEAD path.
- [ ] HEAD snapshot filtered to the configured workspace roots (same set discipline as
      the working-tree scan).
- [ ] `diff_snapshots` pure, deterministic, total-ordered; added/removed correct for
      symbols, imports, calls; identical snapshots → empty delta.
- [ ] `ScanContext.fact_delta()` returns the working-tree-vs-HEAD delta; `None`/empty when
      HEAD does not resolve.
- [ ] **`codas inventory --json` and `codas check` byte-identical** before/after (the
      working-tree `calls` path either unchanged, or changed-and-cross-checked equal).
- [ ] On the clean tree (HEAD == working tree, nothing staged): `fact_delta()` is empty.
      Teeth (a real added/removed symbol/import/call shows up) proven by temp-git
      fixtures.
- [ ] Deterministic; §17 (no LLM) / §11 (snapshot + git reads behind adapters / the facts
      seam; no policy imports an adapter) clean; `codas check .` = 0; full suite green.

## Notes

- Honest sequencing: this is v2's foundation, shippable on its own. v2-B (couplings +
  `must_update_if_changed` re-authoring — "the bulk of the risk") gets its own design +
  codex review before any gate semantics change, per the handoff.
- Freezing the snapshot schema HERE is the co-design the fact-cache design.md asked for:
  the cache's `RawFileFacts` is the per-file slice of this snapshot.
