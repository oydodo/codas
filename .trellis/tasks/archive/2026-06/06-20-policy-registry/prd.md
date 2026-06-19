# policy_registry consistency policy (policies.yml ↔ implemented check_*)

## Goal

Ship the **policy_registry coupling** the doc-reconciliation audit + `spec-drift-fact-delta`
v2 PRD identified: `.codas/policies.yml` declarations and the implemented `check_*`
policy functions must agree. A current-state set-equality invariant — deterministic,
zero materiality judgment, no fact-diff/cache (so it is shippable now, ahead of the
deferred fact-delta machinery). Realizes v2's thesis (a delta that breaks the registry
fires) as a state invariant: checking set-equality at HEAD needs no diff against HEAD.

## Background: the real drift (2026-06-20 ground truth)

`check.py` wires 17 `check_*` policies; `.codas/policies.yml` declares 15. They diverge:
- **Implemented but undeclared (7)** — `config_sources`, `document_set`,
  `dogfooding_protocol`, `program_plan`, `structure_map`, `trellis_context`, `waivers`
  (the bootstrap / loader meta-checks).
- **Declared but unimplemented (5)** — `duplicate_concept`, `orphan_artifact`,
  `missing_canonical_owner`, `constraint_conflict`, `stale_preflight` (planned/roadmap).
- **Consistent (10)** — dependency_direction, deprecated_path_used,
  duplicate_implementation, duplicate_symbol, generated_wiki_drift,
  missing_structure_owner, spec_drift, stale_claim, stale_wiki_claim, structure_drift.

Nothing currently catches this; it is exactly the deterministic registry coupling.

## Requirements

- New policy `check_policy_registry(ctx)` (consumes facts via ScanContext; §11/§17 clean).
- **implemented set** = top-level `check_<id>` symbols under `src/codas/policies/` from
  `ctx.symbols()`; id = the function name minus the `check_` prefix (NOT the module
  filename — `missing_owner.py` defines `check_missing_structure_owner`).
- **declared set** = keys of the `policies:` mapping in `.codas/policies.yml`; an entry
  may carry `status: planned` (declared, not yet implemented — exempt from needing an
  impl) and/or `kind: bootstrap` (documentation: a meta/loader check, not a governance
  rule — descriptive, no logic change).
- Findings (severity **error**):
  - an implemented `check_<id>` with no policies.yml declaration → "wired policy without
    declaration" (evidence: the policy module path);
  - a declared policy that is neither implemented nor `status: planned` → "declared
    policy without implementation" (evidence: policies.yml).
- Reconcile `.codas/policies.yml` to reach **0 findings on this repo** (the dogfood
  invariant): add the 7 bootstrap entries (`kind: bootstrap`), mark the 5 planned
  (`status: planned`), and declare `policy_registry` itself (governance). Teeth proven
  by fixtures (a missing declaration / a stray declaration each fire).

## Acceptance Criteria

- [ ] `check_policy_registry(ctx)` wired in `check.py`, declared in `policies.yml`,
      added to the `test_codas_check` orchestration monkeypatch (8th ctx consumer).
- [ ] policies.yml reconciled; `codas check .` = 0 (every implemented check declared;
      every declared-non-planned policy implemented).
- [ ] Fixtures prove both finding directions + the `status: planned` exemption.
- [ ] Deterministic; inventory byte-identical (policies.yml is not an inventory fact —
      only `policy_version` provenance moves, which is correct); full suite green.
- [ ] §11 (facts via ctx; loads the policies.yml claim surface directly, like
      duplicate_implementation loads claims.yml — not an adapter) / §17 (no LLM) clean.

## Out of scope

- The fact-DELTA generalization (re-author `must_update_if_changed` into fact-level
  couplings; retire `drift_couplings`) — that is `spec-drift-fact-delta` v2's
  cache-dependent half (deferred, co-design with `06-20-fact-cache-persistent`).
- "Implemented but not WIRED in check.py" (a defined-but-uncalled `check_*`): this v1
  uses symbol existence as the implemented signal; tightening to the check.py import
  signal is a later refinement (noted, not shipped).
