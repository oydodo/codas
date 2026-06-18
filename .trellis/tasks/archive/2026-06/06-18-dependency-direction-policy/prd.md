# PRD — P3 B2: dependency-direction policy

## Context

P3 §11 Adapter Boundary. A1/A2 removed direct adapter imports from policies; B1
made the Python adapter emit import (reference) facts. The boundary is still
guarded only by an interim unit test. This slice turns it into a **dogfooded Codas
finding**: a policy that reads `structure.yml` `dependency_rules` and the B1 import
facts, and reports a module that imports a unit it `must_not_depend_on` — with
evidence.

`structure.yml` already declares `dependency_rules` (e.g. `codas-source
must_not_depend_on role-integrations`) but **nothing enforces them**. B2 makes them
real and adds the boundary rule `codas-policies must_not_depend_on codas-adapters`.

## Goal

`check_dependency_direction(ctx)` reports, as errors, first-party import edges that
violate a `must_not_depend_on` rule, mapping importer/target files to Structure Map
units. 0 findings on this repo (dogfood invariant — A2 already made it true);
fixtures prove the teeth.

## Requirements

1. `ScanContext.imports() -> ImportFacts` — memoized `extract_import_facts` (the
   policy consumes facts via the seam; it must NOT import the Python adapter — the
   boundary-enforcing policy itself respects the boundary).
2. `policies/dependency_direction.py::check_dependency_direction(ctx)`:
   - load the Structure Map; build a literal unit→prefix map.
   - for each first-party import edge (`target_path` not None), find the importer's
     **most-specific owning unit** and read that unit's `must_not_depend_on` ids
     (rules are local to the unit — schema-faithful, not inherited from ancestors).
   - skip self/intra-unit edges (importer and target owned by the same unit).
   - resolve each forbidden unit id to its path; flag the edge if `target_path` is
     under a forbidden unit's path prefix. Error finding with importer/target unit
     ids + the rule; evidence = importer path:line and target path.
   - deterministic total sort `(importer_path, line, target_path)`.
3. `structure.yml`: add `codas-policies: must_not_depend_on: [codas-adapters]`.
4. `policies.yml`: declare `dependency_direction` (error).
5. `check.py`: wire `check_dependency_direction(ctx)`.

## Acceptance criteria

- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings" (the boundary
  holds post-A2; the new rule is satisfied).
- Fixtures prove: a policy-unit file importing an adapter-unit file → error; an
  allowed import (e.g. policy importing `codas.structure.index` / `codas.facts`) →
  no finding; an external import → no finding; ancestor rule (`codas-source
  must_not_depend_on role-integrations`) enforced.
- `codas inventory . --json` byte-identical across two runs.
- Full suite green.

## Non-goals

- `may_depend_on` allow-list enforcement (whitelist mode) — only
  `must_not_depend_on` (deny) is enforced now; allow-list is a later facet.
- Glob/external-unit dependency rules — literal first-party units only.
- Removing the interim import-guard unit test — kept as a fast smoke; the policy is
  the authoritative governance.
- Non-Python ecosystems — Python import facts only.
