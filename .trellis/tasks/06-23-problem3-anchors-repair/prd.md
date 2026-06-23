# Problem-3 anchors + RepairTarget

Catch "a decision changed the code but the PRD/design doc was not updated" at commit time,
and hand the agent the exact fix. Highest product value of the 4 tasks.

Context + reasoning: `docs/codas-architecture-decisions.md` §3/§5 (committed `c656b0b`).
Source dialogue: handoff `.trellis/workspace/oydodo/handoff-2026-06-23-four-tasks.md` task ④.

## Problem

Decisions reach the code but not the docs. Today only `.codas/wiki/code/**` pages can carry
code-anchors; live decision/design docs cannot, so a rename or signature change silently
diverges from the doc that describes it. There is one hand-written coupling in `claims.yml`
("public symbol in `openworld.py` changes → `docs/codas-design.html` must co-change") — proof
the need is real, but it does not scale by hand.

## Three pieces

1. **Anchor-bearing docs** — let LIVE decision/design docs carry `defines:/calls:/contains:`
   anchors (extend the anchor-bearing root beyond `.codas/wiki/code/**` via a config knob).
2. **Anchor-derived co-change gate** — the anchor IS the coupling declaration; DERIVE the
   co-change requirement from it instead of hand-writing `claims.yml` `fact_coupling` entries.
3. **RepairTarget** — when an anchor breaks, emit the stale span + the old node + the
   best-match new node (from the fact-delta, e.g. a rename) + the action, injected to the
   agent so the fix is mechanical.

## Tier invariant (MUST hold)

- Detection (`code_anchor`) = advisory/warning, works on all languages (open-world).
- The co-change **GATE** resolves ONLY against in-core deterministic facts (Python `ast`).
- A gate-claim may NEVER key on an open-world / external (e.g. CodeGraph) fact — guessed edges
  would false-block correct commits.

## Scope boundary

- Anchor-bearing = LIVE decision/design docs only, NOT archived PRDs (archived PRDs describe
  PAST state → would false-drift against current code).
- Folds the "claim overload" cleanup: `claims.yml` `fact_coupling` and doc anchors are the
  same concept two ways → converge on the anchor.

## Requirements

- A config knob extends the anchor-bearing root to named live docs.
- Co-change requirements are derived from anchors (the hand-written `claims.yml` seed is
  generalized, not duplicated).
- RepairTarget data structure: stale span, old node, best-match new node (rename detection
  over the fact-delta), action string; delivered via preflight / injection.
- Determinism: the gate side resolves against `ast` facts only.

## Acceptance Criteria

- [ ] A live design doc with a `defines:` anchor that points at a renamed symbol is FLAGGED at
      commit, with a RepairTarget naming the new symbol.
- [ ] The existing `openworld.py ↔ codas-design.html` coupling is expressed as an anchor (or
      anchor-derived), not a hand-written `claims.yml` row, with no loss of coverage.
- [ ] Archived PRDs do NOT false-drift.
- [ ] Gate keys only on in-core deterministic facts (invariant test).
- [ ] `PYTHONPATH=src python3 -m codas check .` → 0 findings; tests green; byte-identical.

## Notes

- gate-semantics + NOVEL (anchor-derived coupling + rename best-match) → **design.md + codex
  DESIGN review BEFORE impl**. codex-MCP stalls → Claude-native adversarial reviewer.
- Effort ~3-5 days. Key files: `policies/code_anchor.py` (anchor scope),
  `policies/fact_coupling.py` (co-change gate + claims.yml load), `app/preflight.py` /
  injection (RepairTarget delivery).

## Review notes (codex direction-soundness pass, 2026-06-23)

- Scope SOUND. Critical trap: letting open-world anchor DETECTION become a blocking gate
  predicate. The design MUST add an explicit enforcement note that detection (`code_anchor`)
  stays advisory and ONLY `ast`-resolvable co-changes may gate. A future "resolved anchor"
  check keyed on open-world / call-graph data is FORBIDDEN — it would false-block correct
  commits on any cross-language/cross-module anchor reference.
- RepairTarget must stay repair METADATA only (never a gate input). Archived PRDs stay
  excluded from the anchor scan.
