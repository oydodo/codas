# spec-drift v2-B: fact-level co-change couplings over the fact-delta

## Status

PLANNING — the gating half of `spec-drift-fact-delta` v2, on top of the v2-A substrate
(`06-20-fact-delta-substrate`, shipped `54968e8`). Touches gate semantics → needs a codex
design review of the APPROACH/SCOPE before any implementation (per handoff).

## The thesis (from `06-19-spec-drift-fact-delta`)

Materiality is a static property of an authored COUPLING, not a per-change judgment.
Express couplings over **fact-deltas** ("a `check_*` symbol was added → policies.yml must
co-change") — always-true by construction, zero semantic judgment (§17-clean). v2-A built
the substrate: `ScanContext.fact_delta()` (symbol/import/call added/removed, HEAD vs
working tree) + `changed_paths()` (files in the diff). v2-B is the policy that gates a
coupling: a watched fact-delta whose required companion is absent from the same diff →
finding.

## The hard constraint (why this is "the bulk of the risk")

The coarse `must_update_if_changed` couplings in `.codas/structure.yml` (24 units, mostly
"`src/...` changed → `docs/codas-implementation-plan.html` must change") have **no
always-true fact-level form**. Gating them literally fires on every comment fix / refactor
→ re-breaks the dogfood `check 0` gate — exactly the false friction v1 dodged by keeping
them advisory. **So v2-B is SURGICAL, not a wholesale re-authoring:** promote ONLY
couplings that are genuinely always-true at fact granularity; leave the rest advisory.

## Requirements

- A fact-level coupling schema: a watched fact-delta predicate (kind ∈ {symbol_added,
  symbol_removed, import_added, import_removed, call_added, call_removed}, a path/scope
  filter, optional name/identity match) + a `requires` list of companion paths/globs that
  must appear in the same change.
- A deterministic policy `check_*(ctx)` consuming `ctx.fact_delta()` + `ctx.changed_paths()`
  (no adapter import, §11): fire one finding per requirement absent from `changed_paths`
  when the watched fact-delta is nonempty. No semantic judgment, no LLM.
- At least ONE worked coupling that is genuinely always-true at fact level AND adds value
  the existing STATE policies (`policy_registry`, `generated_wiki_drift`) do NOT already
  cover — i.e. a DRIFT-only signal (a change that needs a companion even though the end
  state stays self-consistent).
- Decide `drift_couplings` (the v1 file-level vouched-coupling mechanism, currently empty):
  retire and subsume into the fact-level couplings, or keep as a manual file-level escape
  hatch alongside.
- `must_update_if_changed`: keep advisory for entries with no fact-level form; document
  the promotion criterion. Do NOT gate them wholesale.

## Acceptance criteria

- [ ] Fact-level couplings authored over deterministic fact-deltas (symbol/import/call),
      not file bytes; documented schema.
- [ ] The policy fires on a change that breaks a coupling, with zero per-change semantic
      judgment and zero false positives on routine edits (comment fixes / refactors that
      don't touch the coupled fact); proven by temp-git fixtures.
- [ ] `drift_couplings` decision made and implemented (retire or keep, with rationale).
- [ ] `codas check .` = 0 on the clean tree; teeth proven by fixtures; deterministic;
      inventory byte-identical; §17/§11 clean.
- [ ] Drift-vs-state guidance documented (when a coupling belongs as a fact-delta gate vs
      a state policy like `policy_registry`).

## Out of scope

- Wholesale `must_update_if_changed` → fact-level re-authoring (rejected above as
  gate-breaking / over-engineering; the v2 thesis itself warns the coarse couplings can't
  be literal always-on gates).
- The persistent fact-cache (`06-20-fact-cache-persistent`, independent optimization).
- `--since <ref>` arbitrary range diffs.
