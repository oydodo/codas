# Codas Product

## Canonical Definition

Codas is a Code Atlas System for coding agents: it maps a repository into
verifiable facts, gives agents task-specific architectural context, blocks
changes that introduce duplicate implementations, orphan artifacts, unresolved
constraint conflicts, or drift (a change leaving a claim inconsistent with the
facts), and surfaces stale claims (inconsistencies no diff can be blamed for) on
any run.

Evidence:

- `docs/codas-design.html`
- `.codas/config.yml`

## Change Governance Model

Codas governs one condition — an artifact inconsistent with the Facts it should
reflect — found at two different times. Two orthogonal axes: did the artifact
change in the diff (changed / unchanged), and is it consistent with the Facts
(consistent / inconsistent). The non-trivial quadrants:

- **Drift** = changed + inconsistent: a change introduced or failed to propagate
  an inconsistency. Diff-attributable, so it is gated at commit time by the
  `fact_coupling` policy over the fact-delta (`ScanContext.fact_delta`) and
  `changed_paths`.
- **Staleness** = unchanged + inconsistent: the inconsistency exists with no diff
  to blame, so it is found by re-verifying claims against Facts on any run — the
  state policies `policy_registry`, `generated_wiki_drift`, `stale_claim` and
  `stale_wiki_claim`.

Drift and staleness are the same disease found at two times, so both detector
families are required: the diff-based gate blocks a bad change as it happens; the
state checks catch inconsistency that already slipped in. A `*_drift` policy name
does not imply the change axis — `generated_wiki_drift` and `structure_drift` are
state checks. Coarse `must_update_if_changed` hints stay advisory (no always-true
fact-level form). v2 status: `fact_coupling` shipped; v1 `spec_drift` and
`drift_couplings` retired. The canonical definition lives in `CONTEXT.md`.

Evidence:

- `CONTEXT.md`
- `src/codas/policies/fact_coupling.py`
- `.codas/claims.yml`

## Scope

Codas applies to any codebase maintained long-term by coding agents. It is
agent-agnostic and language-agnostic at the core layer.

Evidence:

- `docs/codas-design.html`

## Current Implementation State

Codas ships a deterministic Atlas inventory, roughly seventeen governance
policies enforced by `codas check`, preflight context packs and run receipts,
and the verified Atlas wiki spine (grounding pack, committed generated pages and
a freshness gate) — all dogfooded on this repository. Current per-phase and
per-deliverable status lives in `.codas/program.yml`; consult it rather than any
fixed summary here. Legacy `harness_guard` prototype code has been removed.
Future Swift, Ciri or XcodeGen behavior must be implemented through adapters, not
the core model.

Evidence:

- `src/codas/`
- `scripts/codas`
- `docs/codas-design.html`
- `docs/codas-implementation-plan.html`
- `docs/codas-structure-map-schema.html`

## Workflow System

Codas uses Trellis as its project task system. Trellis stores durable task
intent and context; Codas consumes it as workflow facts through the Trellis
adapter.

Evidence:

- `.trellis/workflow.md`
- `.trellis/spec/codas/workflow/task-system.md`
- `.codas/config.yml`

## Duplicate Risks

- Do not implement Codas as only a Codex skill.
- Do not implement Codas as only a Claude Code hook.
- Do not keep Swift/XcodeGen checks in the core layer after adapter extraction.
- Do not let generated wiki pages become higher authority than facts and
  explicit constraint sources.
- Do not treat Trellis as a substitute for Codas inventory or policy gates.

## Required Synchronization

This co-change list is **advisory** (a coarse path heuristic, like
`must_update_if_changed`); the enforced drift gate is `fact_coupling` over the
fact-delta at commit time, not this list. When changing command shape, policy
semantics, repo-local state, adapter boundaries, data model or enforcement rules,
update:

- `docs/codas-design.html`
- `docs/codas-structure-map-schema.html`
- `.codas/structure.yml`
- `.codas/wiki/index.md` or this concept page when navigation changes
- `.codas/policies.yml` when policy behavior changes
