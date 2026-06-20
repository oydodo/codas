# Design — anchor-to-source coupling (re-done via Trellis)

## Mechanism (shipped gate, no new code)
fact_coupling watches a working-tree-vs-HEAD FACT-delta + requires a companion path in the
same diff. Two entries appended to `.codas/claims.yml` `fact_couplings`:

  - when_fact: {kind: symbol_added,   scope: src/codas/facts/openworld.py, name: "[!_]*"}
    requires: [docs/codas-design.html]
  - when_fact: {kind: symbol_removed, scope: src/codas/facts/openworld.py, name: "[!_]*"}
    requires: [docs/codas-design.html]

- `name: "[!_]*"` — fnmatch negated class -> PUBLIC symbols only (no leading underscore), so
  a private helper added to openworld.py does NOT demand a design.html co-change.
- `scope` is the single file, so an unrelated facts-module change (delta.py, snapshot.py)
  does not trigger it — tight, no false positives.
- Always-true by construction (§17): a comment/prose edit produces no symbol-delta -> dormant.

## Why two couplings
symbol_added catches new public API (the common case — adding a model capability); 
symbol_removed catches deleting public API. Both change the authoritative contract -> the
doc must follow. when_fact takes one kind, so two entries.

## Ground-truth obligation (B2 lesson)
A coupling claim must be DEMONSTRATED to fire on the drift it targets, not just asserted:
- clean tree -> dormant -> check 0.
- add a public symbol to openworld.py, do not touch design.html -> fact_coupling ERROR.
- co-change design.html -> satisfied -> clean.
- revert the probe.

## Process note
This change touches GATE SEMANTICS -> a codex DESIGN review is required BEFORE implementing
(the rhythm's iron rule). The original commit skipped both the Trellis task and that review;
this task does both.
