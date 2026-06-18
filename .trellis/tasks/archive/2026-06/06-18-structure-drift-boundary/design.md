# Design: Structure drift policy (active boundary existence)

## Principle

Pure consumer of the Structure Map. This facet needs no file scan: existence of a
literal unit path is a single `(repo / prefix).exists()` check — exactly how
`build_artifact_index` computes `observed.exists` for literal prefixes
(`exists = (repo / prefix).exists()`). So the policy iterates units directly; no
`discover_files`, no index build. (Avoids the shared-scan concern entirely for
this slice.)

## Policy: `structure_drift` (`src/codas/policies/structure_drift.py`)

Signature: `check_structure_drift(repo: Path, config: CodasConfig) -> list[Finding]`

Algorithm:
1. Guard: `.codas/structure.yml` absent → `[]` (mirrors the other structure
   policies; absence reported by `config_sources`).
2. `load_structure_map`; on `StructureMapError` → `[]` (malformedness is
   `structure_map_loads`' job).
3. For each `unit` in `structure_map.units`:
   - `unit.status != "active"` → skip (planned/deprecated/removed/external exempt).
   - `prefix = normalize_path(unit.path)`; `prefix == ""` → skip (root catch-all
     is always present).
   - `prefix` contains a glob char (`* ? [`) → skip (glob existence is a later
     facet).
   - `(repo / prefix).exists()` is False → emit:
     ```
     Finding(
         severity="error",
         check_id="structure-drift",
         message=f"Active Structure Unit '{unit.id}' declares a path that does not exist: {unit.path}",
         evidence=[Evidence(path=STRUCTURE_SOURCE, detail=f"units[{unit.id}]")],
         recommendation="Restore the path, or update the unit (status or path) in the Structure Map.",
         meta={"unit": unit.id, "path": unit.path, "status": unit.status},
     )
     ```
4. Sort by `meta["unit"]` (unit ids are unique map keys → total order).

Severity = error per `.codas/policies.yml` `structure_drift.severity` and the §8
"unmanaged drift" case (an active boundary the tree lost without a map update is
unmanaged, not mere incomplete sync).

Glob detection: inline `any(ch in prefix for ch in ("*", "?", "["))`, matching
`index.GLOB_CHARS`, kept local like `deprecated_path`'s own prefix match.

## Why 0 on the real repo (and that is correct)

Probe (2026-06-18): every `active` unit path exists; the only non-existent unit
paths are `role-contracts` (`src/codas/roles`) and `role-integrations`
(`src/codas/integrations`), both `status: planned` → exempt. So the policy is
silent today and becomes the guard for "an active governed directory was deleted
or moved without updating its Structure Unit." Firing proven by fixtures.

## Boundary vs other policies (no overlap)

- `structure_map_loads`: parse + reference integrity of the map. Does NOT check
  on-disk existence. This policy adds the existence dimension.
- `missing_structure_owner`: files → units (a file with no owner). This policy is
  the dual: units → tree (a unit with no path). Disjoint trigger sets.
- `deprecated_path_used`: files under deprecated/removed paths. This policy only
  looks at `active` units. Disjoint.

## Tests (`tests/test_structure_drift_policy.py`)

Temp-repo fixtures writing only `.codas/structure.yml` (no file scan needed):
- active unit whose path is missing → one error finding, check_id
  `structure-drift`, unit id + path in meta/evidence.
- active unit whose path exists (create the dir/file) → no finding.
- planned unit whose path is missing → no finding (status exempt).
- root unit (`path: .`) → no finding (empty prefix).
- active unit with a glob path, no match → no finding (deferred facet).
- determinism: two missing active units → findings sorted by unit id.
- missing `.codas/structure.yml` → `[]` (guard).

Plus the dogfood-invariant test in `test_codas_check.py`: assert `structure-drift`
absent from `codas check .` (extends the existing assertion).

## Wiring (`src/codas/app/check.py`)

Add after `check_missing_structure_owner` (all structure-derived, grouped):
```
findings.extend(check_structure_drift(repo, config))
```

## Dogfooding checklist

- Concept touched: `structure_drift` (declared in `.codas/policies.yml`;
  description "Repository changes must stay aligned with the Structure Map or
  update it explicitly" already covers this facet — no claim edit needed).
- New artifacts: one policy module under `codas-policies`, one test under
  `codas-tests` — both governed → `inventory.unowned` stays empty.
- No new module directory → no `.codas/structure.yml` unit edit.
- Behavior matches §8/§10 First Implementation → no schema/plan claim change.
- Bootstrap gate: `unittest discover` + `git status --short` clean.
- Link `program:P2:policy-engine-structure-drift` → this task.
