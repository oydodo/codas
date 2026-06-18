# Design — P3 B2: dependency-direction policy

Authority: `docs/codas-structure-map-schema.html` §4 (`may_depend_on` /
`must_not_depend_on`), §8 (structure policies); plan §11 (Adapter Boundary), §6
(Findings). Consumes B1 import facts.

## `ScanContext.imports()`

Add a memoized accessor mirroring `symbols()`:

```python
from codas.adapters.python import ImportFacts, extract_import_facts
...
    def imports(self) -> ImportFacts:
        if "imports" not in self._cache:
            self._cache["imports"] = extract_import_facts(self.repo, self.files)
        return self._cache["imports"]
```

Re-export `ImportFacts`/`ImportFact` via `__all__` (symmetry with SymbolFact). The
dependency policy consumes facts through the seam and imports **no** adapter — the
boundary-enforcing policy itself respects the boundary it enforces.

## Policy: `policies/dependency_direction.py`

`check_dependency_direction(ctx: ScanContext) -> list[Finding]`:

1. Load the Structure Map (same pattern as `missing_owner`/`structure_drift`):
   `load_structure_map(ctx.repo / ".codas" / "structure.yml", source=STRUCTURE_SOURCE)`;
   on `ConfigLoadError` return a single `structure-map-load-error` finding (or
   `[]` if absent — mirror the sibling policies; pick whatever they do).
2. Build `prefixes = [(normalize_path(u.path), u) for u in units if not _is_glob]`.
   `unit_by_id = {u.id: u}`.
3. `_owner(path)` = unit with the longest literal prefix matching `path`
   (most-specific-wins; reuse the `index._owning_unit` idea — literal units only).
4. **Rules are local to the owning unit** (schema-faithful — the schema describes
   dependency rules as local to the unit, NOT inherited). For an edge, the
   applicable rule is the `dependency_rules` entry whose `unit` is the importer's
   **most-specific owning unit**. Its `must_not_depend_on` ids resolve to forbidden
   path prefixes. (Consequence: `codas-source`'s rule governs files it owns
   directly; each child unit carries its own rule. The new `codas-policies` rule
   directly governs every policy file — which is exactly the boundary we enforce.)
5. For each first-party edge (`edge.target_path is not None`):
   - `importer_owner = _owner(edge.module)`; `target_owner = _owner(edge.target_path)`.
   - **Self-edge skip (precise):** if `importer_owner` and `target_owner` are the
     same unit id → skip (an intra-unit import is never a violation, even under a
     pathological self-referential rule).
   - look up the rule for `importer_owner.id`; build its forbidden prefixes; if
     `target_path` is under any forbidden prefix
     (`tp == p or tp.startswith(p + "/")`, segment-safe like index.py:166) → error.
   - `dependency-direction`, severity error, message:
     `"{importer_owner.id} must not depend on {forbidden_unit}: {importer} imports {target}"`.
   - evidence: `Evidence(path=edge.module, line=edge.line, detail=edge.target)` and
     `Evidence(path=edge.target_path)`.
   - meta `{importer_unit, forbidden_unit, target_path}`.
6. Total sort `(module, line, target_path)`. `target_path is None` (external) is
   filtered before any unit lookup. A `must_not_depend_on` id with no matching unit
   is skipped (no prefix → no match), consistent with models.py.

`DependencyRule` is already parsed into `structure_map.dependency_rules`
(models.py:23). Rules keyed by `unit` id; `must_not_depend_on` is a tuple of unit
ids. A rule naming an unknown unit id is ignored (loader/validation concern; B2
treats only resolvable ids — optionally emit a schema finding, see open questions).

## Edge → unit mapping detail

`target_path` (e.g. `src/codas/adapters/python.py`) → forbidden if it is under the
forbidden unit's path (`src/codas/adapters`). Path-prefix match (`tp == p or
tp.startswith(p + "/")`) so descendants of a forbidden unit are caught even without
their own sub-unit. Importer/target owners via most-specific literal prefix
(`_owner`, literal units only — glob units like `.trellis/tasks/*` are out of scope
and never own a first-party `.py`).

## Wiring + claims

- `structure.yml` `dependency_rules`: add
  ```yaml
  codas-policies:
    must_not_depend_on:
      - codas-adapters
  ```
  (After A2 no policy imports an adapter → this stays 0 on the repo.)
- `policies.yml`: declare
  ```yaml
  dependency_direction:
    severity: error
    description: A module must not import a Structure Map unit it is declared to not depend on.
  ```
- `check.py`: `findings.extend(check_dependency_direction(ctx))`.

## Dogfood / determinism

- 0 findings on repo: codas-policies→codas-adapters is empty post-A2; codas-source
  →role-integrations is empty (integrations is a planned/empty module); atlas-wiki
  →codas-source rule is over non-code units (no import facts there) — unaffected.
- Verify the rule actually has teeth via fixtures (a temp repo with a policy unit +
  adapter unit + an offending import). Determinism: pure functions over sorted
  facts + sorted units.
- Keep the interim `test_no_policy_imports_an_adapter` unit test as a fast smoke;
  the policy is the authoritative, evidence-backed governance.

## Tests (`tests/test_dependency_direction_policy.py`)

- offending edge (policy-unit file imports adapter-unit file) → one error with
  both units in meta + two evidence rows.
- allowed: policy importing a non-forbidden unit (structure index / facts) → none.
- external import (`target_path` None) → none.
- rules are local: a file owned by a child unit is NOT subject to a *parent* unit's
  `must_not_depend_on` (proves owning-unit-only, schema-faithful semantics).
- descendant target: importing a file in a sub-path of the forbidden unit → flagged
  (proves path-prefix, not exact-unit, match).
- self/intra-unit edge: a module importing another file in its own unit → none.
- determinism: findings sorted by (module, line, target_path).
- `ScanContext.imports()` cached (in `test_scan_context.py`).

## Resolved by codex design review

- **Semantics: owning-unit-only** (NOT ancestor-union). The schema describes rules
  as local to the unit; owning-unit-only is schema-faithful, avoids surprising
  findings on a deep tree, and still fully enforces the boundary (every policy file
  is directly owned by `codas-policies`). Self-edge skip defined precisely as
  owning-unit-id equality.
- Target match by segment-safe path-prefix — confirmed OK (matches index.py:166).
- Literal-only `_owner` — confirmed sufficient; glob units out of scope.
- 0-findings-on-repo confirmed: `src/codas/integrations` absent, `atlas-wiki` has no
  `.py`, post-A2 no policy imports the adapter.
- Unknown unit id in a rule → silently skipped (no prefix → no match).
- `may_depend_on` deny-only — out of scope for B2 (allow-list is a later facet).
