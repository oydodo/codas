# Design: Missing structure owner policy

## Principle

Pure consumer of existing facts. `build_artifact_index` already computes the
firing set (`unowned`); the policy adds the nearest-candidate remediation hint and
formats findings. No loader/index changes except (if needed) exposing a small
deterministic helper.

## Policy: `missing_structure_owner` (`src/codas/policies/missing_owner.py`)

Signature: `check_missing_structure_owner(repo: Path, config: CodasConfig) -> list[Finding]`

Algorithm:
1. Guard: if `.codas/structure.yml` absent → `[]` (absence reported by
   `config_sources`; mirrors `check_structure_map` / `check_deprecated_path_used`).
2. `structure_map = load_structure_map(path, source=STRUCTURE_SOURCE)`. On
   `StructureMapError` → `[]` (malformedness is `structure_map_loads`' job).
3. `roots = workspace_roots(config.raw)`; `files = discover_files(repo, roots)`.
4. `index = build_artifact_index(repo, roots, structure_map, files=files)`.
5. For each `artifact` in `index.unowned`:
   - `candidates = nearest_candidate_units(artifact, structure_map.units)`.
   - Emit:
     ```
     Finding(
         severity="error",
         check_id="missing-structure-owner",
         message=f"Artifact has no owning Structure Unit: {artifact}",
         evidence=[Evidence(path=artifact)],
         recommendation=(
             "Add a Structure Unit that owns this path"
             + (f" (nearest: {', '.join(candidates)})." if candidates else ".")
         ),
         meta={"nearest_candidates": candidates},
     )
     ```
6. Sort findings by `artifact` (one finding per artifact → total key). `index.unowned`
   is already sorted, but re-sort defensively.

Severity = error, matching `.codas/policies.yml` `missing_structure_owner.severity`
and §8.

## Nearest candidate units

A deterministic, dependency-free helper (in the policy module; promote to
`structure/index.py` only if a second caller appears):

```
def nearest_candidate_units(artifact, units) -> list[str]:
    art_parts = normalize_path(artifact).split("/")
    scored = []
    for unit in units:
        prefix = normalize_path(unit.path)
        if prefix == "":
            shared = 0            # root catch-all: weakest possible candidate
        else:
            unit_parts = prefix.split("/")
            shared = common_leading_count(art_parts, unit_parts)
        scored.append((shared, unit.id))
    # keep units that share at least one leading component; if none, fall back to
    # the broadest cover (shared == 0) so the hint is never empty when units exist.
    positive = [s for s in scored if s[0] > 0]
    pool = positive or scored
    pool.sort(key=lambda s: (-s[0], s[1]))
    return [unit_id for _shared, unit_id in pool[:3]]
```

`common_leading_count` counts matching path components from the left
(`["src","codas","x"]` vs `["src","codas"]` → 2). Glob unit paths: compare on the
literal prefix (`_literal_prefix` from index, or just the pre-glob head) so a
candidate like `src/*/foo` contributes its literal lead. For the first cut, units
with glob paths can use `normalize_path` then split on the literal head; keep it
simple and note globs are rare in this map (none today).

Determinism: sort key `(-shared, unit_id)` is total; capped at 3 candidates.

## Wiring (`src/codas/app/check.py`)

Add after `check_structure_map` (it is structure-derived, like
`check_deprecated_path_used`):
```
findings.extend(check_missing_structure_owner(repo, config))
```

## Why this is 0 on the real repo (and that is correct)

`repo-root` has `path: .` → `normalize_path` → `""` → matches every file as the
least-specific owner (`index._owning_unit`). So no file is ever unowned while the
root unit exists. The policy is the automated guard for that invariant: if the
root unit is dropped or a workspace root is added with no covering unit, unowned
becomes non-empty and the gate fires. Proven by fixtures (map without root unit).

## Status boundary vs structure_drift (resolved)

A matching unit counts as an owner regardless of `status`. The `role-contracts`
and `role-integrations` units are `status: planned` with paths `src/codas/roles`
and `src/codas/integrations` that don't exist yet. If a file later lands under
`src/codas/roles`, it MATCHES the planned unit → it is owned → `missing_structure_owner`
does NOT fire. Whether a file appearing under a non-active unit is a problem is
`structure_drift`'s job ("changed paths remain inside ACTIVE structure boundaries"),
a later slice. So this policy ignores `status` entirely and keys only on
"matches some unit." Crisp, non-overlapping boundary: coverage (this policy) vs
active-boundary (structure_drift).

## Tests (`tests/test_missing_owner_policy.py`)

- map WITHOUT a root catch-all + a file outside all units → one error finding,
  check_id `missing-structure-owner`, artifact path in evidence, nearest
  candidates non-empty and correctly ordered (closest unit first).
- map WITH a root catch-all + same files → no finding (coverage holds).
- nearest-candidate ordering: file `src/foo/bar.py` with units `src` and
  `src/foo` → `src/foo` (shared 2) ranks before `src` (shared 1).
- determinism: two unowned files → findings sorted by path.
- missing structure.yml → no finding (guard).
- Real-repo assertion in `test_codas_check.py`: `missing-structure-owner` absent
  from `codas check .` (extends the existing dogfood-invariant test).

## Dogfooding checklist

- Concept touched: `missing_structure_owner` (declared in `.codas/policies.yml`;
  description "Changed artifacts in governed paths must map to a Structure Map unit
  with an owner" already matches the implemented behavior — no claim edit needed).
- New artifacts: one policy module under `codas-policies`, one test under
  `codas-tests` — both governed by existing units → `inventory.unowned` stays empty.
- No new module directory → no `.codas/structure.yml` unit edit.
- Behavior matches §8/§10 First Implementation → no schema / plan claim change.
- Bootstrap gate: `unittest discover` + `git status --short` clean.
- Link `program:P2:policy-engine-structure-drift` → this task.
