# spec_drift v2: fact-delta deterministic couplings (retire drift_couplings)

## Triage 2026-06-21 — CLOSED (mechanism shipped; remainder is as-needed, not a task)
The v2 GATING MECHANISM shipped: the `fact_coupling` policy consuming `ctx.fact_delta()` is
live (`.codas/claims.yml` `fact_couplings` — the `check_*`→check.py wiring coupling AND the
anchor-to-source openworld→design.html coupling both in production), and the v1 `drift_couplings`
file-level layer is RETIRED. The reframed decision (couplings are added SELECTIVELY when a
specific fact-delta makes a companion obligation always-true; the coarse `must_update_if_changed`
stays ADVISORY) means there is no discrete "migrate every hint" deliverable — a new coupling is
authored per-need, each its own small change with codex review. Nothing open here; archived.

## Status

PLANNING / queued — **v2-A substrate + policy_registry SHIPPED; v2-B couplings DEFERRED.**

- **`policy_registry` coupling: SHIPPED** as standalone task `06-20-policy-registry`
  (commit `1d1cd91`) — the worked example below, implemented state-based (set-equality
  between policies.yml declarations and implemented `check_*`, no fact-diff needed).
- **v2-A fact-delta substrate: SHIPPED** as task `06-20-fact-delta-substrate` (commit
  `54968e8`). The `inventory@HEAD` fact-diff substrate this remainder needed now exists:
  `FactSnapshot{symbols,imports,calls}` at the working tree OR `HEAD` (pure fn of
  file-set+content; HEAD via `git ls-tree`/`cat-file`), a pure identity-key
  `diff_snapshots`, and `ScanContext.fact_delta()` (working-tree-vs-HEAD). No coupling
  schema, no policy change yet. This also FROZE the snapshot schema for the deferred
  `06-20-fact-cache-persistent` (the cache stores `FactSnapshot`'s per-file slice).
- **v2-B remainder DEFERRED** (re-author `must_update_if_changed` into fact-level
  couplings consuming `ctx.fact_delta()`; retire `drift_couplings`; the `spec_drift` v2
  policy rewrite). This is the bulk of the risk — re-authoring the coarse couplings
  precisely so the always-on gate does not re-break the dogfood `check 0` or block past
  commits. Needs its OWN design + codex review before any gate-semantics change. The
  cache (`06-20-fact-cache-persistent`) is now an independent optimization (v2-B can
  recompute the HEAD snapshot directly via `ctx.fact_delta()` — correct, slower).

A reframing of the shipped `spec_drift` (06-19-spec-drift) from a 2026-06-19 user
insight. Supersedes the `drift_couplings` (vouched-claim) layer.

## The insight

> "Meaningless changes shouldn't exist. Every change is meaningful. So you don't need
> semantic judgment."

**Materiality is a property of the COUPLING (static, authored once), not of the CHANGE
(judged per-edit).** The shipped spec_drift treated materiality as a per-change semantic
judgment that the core may not make (§17) → it introduced a `drift_couplings` escape
hatch where a human/agent vouches a coupling is material (gating), leaving the coarse
`must_update_if_changed` advisory. That was over-engineering: `drift_couplings`
{when_changed, requires} is structurally identical to structure.yml
`must_update_if_changed` (unit change → companions must change). The only manufactured
difference (one gating, one advisory) existed solely to dodge the materiality judgment.

If every change is material by axiom, there is nothing to judge per-change — the
obligation applies to ALL changes deterministically. The judgment happens ONCE, when the
coupling is authored. → `drift_couplings` collapses back into `must_update_if_changed`,
and spec_drift becomes a deterministic autonomous gate over every change. No claims, no
LLM.

## The one wrinkle + its (still deterministic) resolution

"F changed → C must change" must be **always-true** to gate deterministically. A
**file-level** coupling is NOT always-true: "src/codas/policies/ changed → plan doc must
change" fires on a comment fix (false friction — exactly what broke the dogfood gate in
v1's analysis). The fix is NOT semantic judgment — it is **coupling granularity**:

> Define couplings over **facts**, not files. Codas already extracts the facts.

- ❌ file-level: "bytes under src/codas/policies changed"
- ✅ fact-level: "a `check_*` symbol was added/removed" → `policies.yml` must change

A fact-level coupling is **always-true by construction**: any change that touches the
coupled fact triggers it; a comment fix touches no symbol → no trigger. Precision moves
into the fact granularity (symbols / call edges / imports — all deterministic Codas
facts), and the materiality judgment stays zero.

## Target design

- **Couplings over fact-deltas**, authored in structure.yml (or a successor surface):
  e.g. "symbol added/removed in unit X → file Y must change", "public export of X
  changed → doc Z", "a new module under X → manifest M". Expressed against the fact
  vocabulary Codas already has (symbols, imports, calls).
- **fact-delta detection**: diff `inventory@HEAD` vs `inventory@working-tree` (deeper
  than v1's file-level `changed_paths`). Surface added/removed/changed facts (symbols,
  edges, exports). The coupling fires when its watched fact-delta is nonempty and the
  required companion is absent from the same change.
- **Enforce on ALL changes** (no `drift_couplings` opt-in, no materiality flag, no
  claim). Deterministic, §17-clean.
- **Retire `drift_couplings`** from spec_drift + `.codas/claims.yml` (or keep claims.yml
  only for duplicate_relationships). Update the spec_drift policy + docs + memory.

## Caveats / dependencies

- **Re-author `must_update_if_changed`** (authoritative claim source) into fact-level
  precise couplings. The current coarse couplings (dir → doc) would, as a literal
  always-on gate, re-break the dogfood gate and would have blocked many past commits.
  This is the bulk of the risk — do it carefully, fixture-tested, dogfood-verified 0.
- **Needs inventory@HEAD vs inventory@now** (a fact-level diff). Ties directly to the
  queued `06-19-incremental-fact-cache` task: content-hash/blob-keyed per-file facts
  make computing inventory@HEAD cheap and the fact-delta nearly free. Consider
  sequencing fact-cache first (or co-designing).
- Scope is a real spec_drift v2 refactor, not a tweak.

## Concrete coupling example found in the wild (2026-06-20 doc audit)

The doc-reconciliation audit surfaced a real, currently-uncaught drift that is the
*ideal* fact-delta coupling: **`.codas/policies.yml` declarations vs the `check_*`
functions wired in `src/codas/app/check.py` are out of sync.** policies.yml still
declares unwired/planned policies (`duplicate_concept`, `orphan_artifact`,
`missing_canonical_owner`, `constraint_conflict`, `stale_preflight`) and omits
bootstrap/load checks that check.py does wire (`config_sources`, `dogfooding`,
`trellis_context`, `structure_map`, `program_plan`, `document_set`, `waivers`). Whether
each gap is intentional (a roadmap declaration / a bootstrap meta-check kept out of the
governance set) is a judgment — but the *coupling* "a wired `check_*` should have a
policies.yml entry (or an explicit planned/bootstrap marker), and vice versa" is a
deterministic fact-delta over `imports`/`symbols` + the policies.yml claim set. v2 should
ship this as a worked `policy_registry` coupling (a new `check_*` wired without a
declaration → finding; a declared policy with no impl and no `planned:` marker →
finding). It needs zero materiality judgment — pure set-equality over facts — exactly the
v2 thesis. (For now the authoritative docs were corrected to NOT claim policies.yml
mirrors the wired set; reconciling policies.yml itself + this coupling is v2's job.)

## Acceptance criteria (draft)

- [ ] Couplings expressed over deterministic fact-deltas (symbol/import/call), not file
      bytes; documented schema.
- [ ] spec_drift fires on EVERY change that breaks a coupling (no opt-in), with zero
      per-change semantic judgment and zero false positives on routine edits (comment
      fixes, refactors that don't touch the coupled fact).
- [ ] `drift_couplings` retired; spec_drift v1 behavior subsumed.
- [ ] structure.yml `must_update_if_changed` re-authored to precise fact-level couplings;
      `codas check .` = 0 on the clean tree; teeth proven by fixtures.
- [ ] Deterministic; inventory byte-identical; §17/§11 clean.

## Notes

- This is the clean endpoint of the drift/stale work (memory `codas-wiki-architecture`
  drift-vs-stale section): DRIFT = a fact-delta that broke a coupling, caught
  deterministically; the "materiality" that seemed to need an LLM was an artifact of
  judging changes instead of authoring couplings.
- Honest record: spec_drift v1 (drift_couplings) shipped as a working stepping stone;
  this v2 is the simplification the insight unlocked.
