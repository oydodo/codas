# spec_drift v2: fact-delta deterministic couplings (retire drift_couplings)

## Status

PLANNING / queued. A reframing of the shipped `spec_drift` (06-19-spec-drift) from a
2026-06-19 user insight. Supersedes the `drift_couplings` (vouched-claim) layer.

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
