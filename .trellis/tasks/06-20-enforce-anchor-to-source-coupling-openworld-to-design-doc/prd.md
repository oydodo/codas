# Enforce anchor-to-source: openworld.py -> design.html §9.4 (fact_coupling)

## Status
PLANNING. RE-DOING through Trellis a change that was first committed WITHOUT a Trellis task
(f744e57, reverted in f108b0f). That bypass was a process violation — worse, the change
edits GATE SEMANTICS (new fact_couplings change `check` behavior), which the rhythm requires
a codex DESIGN review for, also skipped. This task restores the proper flow:
codex design review -> implement -> codex impl review -> commit -> archive.

## Why
"anchor-to-source" (a model change must propagate up to the master design doc) was being
held as a MEMORY discipline, not enforced. Per Codas's own creed — process can't be enforced,
artifacts can — it must be a gate. The open-world fact model lives in code at
`src/codas/facts/openworld.py` and is authoritatively summarised in `docs/codas-design.html`
(§9.4). When the model's PUBLIC code API changes, the master design doc must follow IN THE
SAME DIFF, else the doc silently falls behind the model (exactly what happened when B2
shipped before §9.4 existed; the advisory `must_update_if_changed` hint did not fire).

## Scope
Two `fact_couplings` in `.codas/claims.yml` (no new code; uses the shipped spec-drift-v2 gate):
- `symbol_added` under `src/codas/facts/openworld.py`, name `[!_]*` (PUBLIC symbols only,
  so a private helper does not demand a doc change) -> requires `docs/codas-design.html`.
- `symbol_removed`, same scope/name -> requires `docs/codas-design.html`.

## Honest boundary (recorded, not a gap to fix here)
This is the DETERMINISTIC slice of anchor-to-source: a public symbol-delta is the always-true
fact-level trigger the coarse advisory `must_update_if_changed` lacks. The SEMANTIC slice — a
pure-PROSE model edit with no symbol-delta — cannot be gated deterministically (the materiality
wall that made `must_update_if_changed` advisory and retired spec_drift v1); it is the LLM
semantic-legality layer's job.

## Acceptance
- [ ] The two couplings are authored in claims.yml; `codas check .` = 0 on the clean tree
      (dormant — no openworld.py symbol delta).
- [ ] Ground-truthed (per the B2 review lesson — a coupling must be PROVEN, not asserted):
      adding a public symbol to openworld.py WITHOUT touching design.html -> `check` errors;
      co-changing design.html -> clean; restored.
- [ ] §17-clean (always-true by construction; zero materiality judgment).
