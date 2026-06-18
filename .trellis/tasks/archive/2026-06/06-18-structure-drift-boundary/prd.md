# PRD: Structure drift policy (active boundary existence)

## Context

Fourth P2 governance slice and the namesake of the work item
`program:P2:policy-engine-structure-drift`. Declared in `.codas/policies.yml`
(severity: error), not yet implemented.

Authority:
- `docs/codas-structure-map-schema.html` §8 — `structure_drift` Initial Rule:
  "Changed paths remain inside active structure boundaries and update required
  claims." Finding: "Error for unmanaged drift, warning for incomplete
  synchronization."
- `docs/codas-implementation-plan.html` §10 — `structure_drift` First
  Implementation: "Changed paths remain inside declared Repository Structure
  boundaries." §17: no LLM for P2 correctness.

`structure_drift` has several facets. On a comprehensively-governed repo (root
catch-all unit owns every file) the artifact-outside-boundary facet is always
empty and cannot be exercised on the real tree. The facet with a genuine,
on-repo-meaningful regression guard is the **dual**: a Structure Unit that
declares an `active` boundary the working tree no longer satisfies — i.e. an
active, literal (non-glob) unit whose declared `path` does not exist on disk.
The inventory already computes this as `units[].observed.exists`.

This is whole-working-tree, evidence-backed, deterministic — no diff, no LLM.

## Goals

1. `structure_drift`: emit an error Finding for each `active`, non-glob Structure
   Unit whose declared path does not exist on disk (`observed.exists == false`).
   Evidence = the Structure Map source + the unit id + the claimed path.
2. Wired into `codas check .` and covered by tests.
3. Dogfooding invariant preserved: `codas check .` stays at 0 findings — every
   active unit path exists today (verified by probe). The policy is the automated
   guard for the "map claims an active boundary that was deleted/moved without
   syncing the map" regression. Firing proven by fixtures.

## Scope rules

- Only `status: active` units fire. `planned` units (e.g. `role-contracts`,
  `role-integrations`) legitimately point at not-yet-created paths; `deprecated`
  / `removed` are `deprecated_path_used`'s domain; `external` may point outside
  the repo. All exempt.
- Only **literal** (non-glob) unit paths. A glob path's "existence" means "some
  file matches," which is a different (later) check; the root unit (`path: .`,
  normalizes to empty) is always present and exempt.

## Non-Goals (deferred to later structure_drift expansion)

- **Artifact-outside-boundary** detection (a file drifting outside active unit
  boundaries). Empty on this repo (root catch-all); needs the orphan/coverage
  machinery and diff scoping.
- **`allowed_children` containment / undeclared-subdirectory** drift (a new area
  under a container that maps to no declared child unit). Requires careful
  loose-file-vs-child-unit handling to avoid false positives on legitimate root
  metadata; later slice.
- **"update required claims"** synchronization (the `must_update_if_changed`
  warning facet). Later.
- **Glob-path unit existence**, diff scoping, dependency-direction drift.

## Acceptance Criteria

- Each active, non-glob unit with a missing path → exactly one error Finding,
  check_id `structure-drift`, with the unit id and claimed path in evidence/meta.
- Deterministic: stable sort by unit id; no timestamps.
- `codas check .` → still 0 findings on this repo.
- `PYTHONPATH=src python3 -m unittest discover -s tests` passes (new tests added).
- `codas inventory` remains byte-identical across two runs.
- Dogfooding: new policy file under `codas-policies`, new test under `codas-tests`
  — both already governed; `inventory.unowned` stays empty.
