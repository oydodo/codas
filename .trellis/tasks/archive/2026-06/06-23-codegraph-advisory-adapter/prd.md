# CodeGraph advisory call-graph adapter

CodeGraph (colbymchenry/codegraph — Node, tree-sitter-based, MIT, no LLM, multi-lang, SQLite)
as the **multi-language + cross-language call-graph adapter**, feeding the ADVISORY tier only.

Context + reasoning: `docs/codas-architecture-decisions.md` §1/§2/§4 (committed `c656b0b`).
Source dialogue: handoff `.trellis/workspace/oydodo/handoff-2026-06-23-four-tasks.md` task ②.

## Position (migrate-LITE — 5 advisors converged)

CodeGraph fills the call-graph layer slot. Real repos are multi-language → this slot is
mandatory, but it is **advisory only**: cross-language edges are GUESSED (heuristic, by
name/convention) → a wrong edge in the gate would FALSE-BLOCK a correct commit (worse than a
missed hint). So it never enters the gate and never enters the inventory hash.

## Requirements

- `adapters/codegraph.py` — subprocess to the CodeGraph CLI; map its graph →
  `SymbolFact` / `ImportFact` / `CallFact` carrying `provenance=codegraph` + resolution tags.
- New `ScanContext` accessors (`codegraph_*()`) that NEVER enter the inventory hash or any
  gating policy. Wire seam in `facts/context.py` (additive accessor).
- Graceful-degrade to empty when the CodeGraph binary is absent (open-world: absence = unknown,
  not denial). Codas-on-pure-Python with no CodeGraph installed stays byte-identical.
- Feed `codas impact` + preflight reuse hints with the advisory facts.
- Cross-language / heuristic edges stay advisory (resolution-tagged), never gate.

## Constraints

- Optional dependency: `pyproject` stays pyyaml-only. CodeGraph is an external Node tool, NOT
  a pip dep.
- NOT in gate. NOT in hash. (Explicitly rejected: CodeGraph-into-gate / diff-model /
  retire-inventory — see decisions doc §6.)

## Acceptance Criteria

- [ ] With CodeGraph installed, `codas impact` surfaces cross-language/advisory edges tagged
      `provenance=codegraph`.
- [ ] With CodeGraph absent, scan degrades to empty advisory facts; gate + hash + byte-identical
      unchanged (regression test).
- [ ] No `codegraph_*()` fact reaches any gating policy or the inventory hash (invariant test).
- [ ] `PYTHONPATH=src python3 -m codas check .` → 0 findings; tests green.

## Notes

- Low risk (off-gate/off-hash) — DESIGN review optional but recommended for the accessor seam.
- Effort ~2-3 days + install CodeGraph in the dev env. Key file: `facts/context.py`.
- Do NOT make CodeGraph gate-grade — that was rejected (advisory only).

## Review notes (codex direction-soundness pass, 2026-06-23)

- Scope SOUND; matches the architecture decision that cross-language/heuristic edges are
  advisory-only (`docs/codas-architecture-decisions.md:31-34,71-72`). Only risk: a FUTURE
  contributor treats the advisory call-graph as input to a new `fact_coupling`-style gated
  check. Mitigation: formalize an "advisory facts MUST NOT gate" rule in governance (policy
  registry / CONTRACT) as part of this task, so the invariant is enforced, not just intended.
