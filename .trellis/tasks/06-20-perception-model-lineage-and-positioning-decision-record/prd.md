# Decision Record — Codas perception model, TMS lineage, positioning

## Status

DECISION RECORD (planning) — captures a 2026-06-20 brainstorm + 3 codex/research passes.
NOT an execution task: it records the model, its intellectual lineage, the competitive
positioning, and a sequenced borrow-backlog. Individual borrows become their own tasks.

This is a rationale/direction record (an ADR), deliberately stored under `.trellis/tasks/`
(skipped by the markdown doc-claim scanner) so its dense path/symbol mentions do not
create stale_claim churn. The DURABLE, dogfood-governed surface is the fenced Concept Map
in `CONTEXT.md`; this file is the long-form "why".

## Why record it

The model unifies prior scattered concepts (the Drift/Staleness 2×2, the wiki engine-split,
the v3 propagation engine, the capability-map north star) into one frame, gives Codas a
named, citable intellectual lineage (Truth-Maintenance Systems), and states — honestly —
where Codas is differentiated vs the tool landscape and where its moat is thin. Leaving it
only in chat would itself be the drift Codas exists to catch.

## Contents (see design.md)

1. The patched perception model — fact families + structured claim schema + verify-by-
   projection + semantic residue + bidirectional propagation + determinism-as-policy-choice.
2. Intellectual lineage = Truth-Maintenance Systems (deterministic single-context JTMS),
   with provenance-semirings / self-adjusting-computation / Toulmin-Pollock-AGM as upgrades.
3. Competitive positioning — the real-but-narrow white space, the thin moat, SonarQube as
   nearest, the "be the determinism layer under AGENTS.md" play.
4. Multi-language fact source decision (SonarQube-as-adapter rejected; SCIP/tree-sitter path).
5. Sequenced borrow-backlog (ratchet baseline first; soundness qualifier; AGENTS.md; etc.)
   and the two live dogfood teeth surfaced (structure.yml purpose staleness; missing
   soundness field on facts).

## Acceptance

- [ ] design.md captures all five with sources/rationale.
- [ ] The patched panorama lands in CONTEXT.md as a fenced (claim-safe) Concept Map.
- [ ] A memory entry persists the lineage + sequenced next steps.
- [ ] check 0, inventory byte-identical, wiki --verify clean (doc-only, no fact change
      beyond the new task fact + the fenced CONTEXT.md block).
