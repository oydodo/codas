# PRD: Missing structure owner policy

## Context

Second P2 governance slice. Implements `missing_structure_owner` — the canonical
structural-coverage net from the Structure Map schema §8 — on top of the existing
artifact index. Declared in `.codas/policies.yml` (severity: error) but not yet
implemented.

Authority:
- `docs/codas-structure-map-schema.html` §8 — Initial Rule: "Changed artifacts
  under governed paths match a unit with owner." Finding: "Error with path
  evidence and nearest candidate units."
- `docs/codas-implementation-plan.html` §10 — `missing_owner` First Implementation:
  "Artifacts in governed paths match a Structure Unit with ownership."

The artifact index already computes the firing set: `build_artifact_index`
returns `unowned` — tracked files under the workspace roots that match no
Structure Unit. Because the loader requires every unit to declare a non-empty
`owner` (REQUIRED_UNIT_FIELDS), "matches a unit" and "matches a unit with owner"
are equivalent: the only way an artifact lacks a structural owner is to match no
unit at all. So the first cut is: **artifact under a workspace root that matches
no Structure Unit → error, with nearest candidate units as the remediation hint.**

This is whole-working-tree, evidence-backed, deterministic — no diff, no LLM
(plan §17).

## Goals

1. `missing_structure_owner`: emit an error Finding for each tracked artifact in
   `inventory.unowned`, with evidence = the artifact path and a deterministic list
   of the nearest candidate Structure Units (the units sharing the longest leading
   path with the artifact) to guide where coverage should be extended.
2. Wired into `codas check .` and covered by tests.
3. Dogfooding invariant preserved: `codas check .` stays at 0 findings on this
   repo. The `repo-root` unit (`path: .`) is a deliberate catch-all, so `unowned`
   is empty and this policy is silent on the real tree. It is the guard that turns
   the P1-era manual worry ("the root unit must normalize to the empty prefix or
   root files all become orphans") into an automated check: remove the root
   coverage and this fires. Firing behavior is proven with fixtures.

## Non-Goals (deferred)

- **`orphan_artifact`** (separate slice). orphan layers a config/spec/task
  reference-graph gate on top of unowned: an unowned-but-referenced file is a
  missing structure owner ("used, add a unit"); an unowned-and-unreferenced file
  is an orphan ("likely cruft"). Building the reference graph is its own slice;
  when it lands, orphan carves the unreferenced subset out of the set this policy
  reports, keeping the two non-overlapping. Documented evolution, First → Later.
- **Diff-scoped detection** ("changed artifacts"). Whole-tree only.
- **Owner freshness / escalation routing / role assignment** (§10 Later Expansion).
- **Glob-vs-literal governed-path nuance** beyond what `build_artifact_index`
  already resolves.

## Acceptance Criteria

- Each artifact matching no unit → exactly one error Finding, check_id
  `missing-structure-owner`, with the artifact path and nearest candidate unit ids
  in evidence/meta.
- Findings are deterministic: stable sort by artifact path; nearest-candidate
  ordering is deterministic (shared-prefix length desc, then unit id).
- `codas check .` → still 0 findings on this repo (root catch-all covers all).
- `PYTHONPATH=src python3 -m unittest discover -s tests` passes (new tests added).
- `codas inventory` remains byte-identical across two runs.
- Dogfooding: new policy file under `codas-policies`, new test under `codas-tests`
  — both already governed; `inventory.unowned` stays empty.
