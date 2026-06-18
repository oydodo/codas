# P1 Structure Map and inventory foundation

## Goal

Make the authored Structure Map and Program Plan executable: load and validate
`.codas/structure.yml` and `.codas/program.yml`, build a deterministic artifact
index that maps repository files to Structure Units, and emit a normalized Atlas
inventory JSON via `codas inventory`. This is the P1 foundation the P2 structure
policies (missing_owner, structure_drift, orphan_artifact, deprecated_path_used)
will sit on.

## Authoritative sources

- `docs/codas-structure-map-schema.html` — §3 authored YAML shape, §4 unit
  fields, §5 normalized JSON shape (inventory output contract), §8 policy checks
  (`structure_map_loads`).
- `docs/codas-implementation-plan.html` — §5 module design (Inventory,
  Filesystem, Structure modules are MVP; Program loader is P1), §6 data
  contracts, §7 command design (`codas inventory`), §8 phase table (P1 exit).
- `CONTEXT.md` — Structure Unit, Repository Structure, Program Plan terms.

## Scope (this task)

1. **Structure Map loader** (`src/codas/structure/loader.py`): parse
   `.codas/structure.yml` into a typed model (units keyed map, defaults,
   dependency_rules, deprecated_paths). Validate per schema §3/§4: required
   `version`, `kind`, `units`; each unit has required `path`, `kind`, `owner`,
   `purpose`, `canonical_placement`; `allowed_children` references resolve;
   `status` in the allowed enum; `deprecated_paths` well-formed. Raise a typed
   load error surfaced as the `structure_map_loads` finding.
2. **Program Plan loader** (`src/codas/structure/program_loader.py` or a sibling
   module): parse `.codas/program.yml` work_items into a typed model; validate
   `id`/`phase`/`depends_on` resolve and the dependency graph is acyclic.
3. **Filesystem artifact index** (`src/codas/structure/index.py` or a
   `filesystem`/`inventory` module): walk `config.workspace.roots`, respect
   `.gitignore` and the standard ignore set, and map each artifact to the
   **deepest** Structure Unit whose `path` prefixes it. Record `observed.exists`
   and `observed.artifact_count` per unit.
4. **Normalized Atlas JSON + `codas inventory`**: emit the schema §5 shape
   (`schema_version`, `source`, `units[]` with id/path/kind/owner/status/
   `observed`/`must_update_if_changed`, `conflicts[]`) plus a program-plan facts
   block. Replace the P0 `inventory` stub in `cli.py`. Output MUST be
   deterministic (stable unit ordering, sorted keys, no wall-clock/random data).
5. **Wire `structure_map_loads`** into `codas check` as the P1-level structure
   policy (loader error → finding). Do NOT implement the P2 substantive policies
   here.
6. **Tests** (`tests/`): structure loader (valid + each validation failure),
   program loader (valid + cycle/dangling dep), artifact-index path mapping
   (deepest-unit, gitignore respect), inventory JSON determinism (same input →
   byte-identical output).

Mark `codas-structure-module` (`src/codas/structure`) `status: active` in
`.codas/structure.yml` once the directory exists; register any new modules.

## Non-Goals (defer)

- `.codas/documents.yml` and the Documents loader (separate P1 item).
- P2 substantive structure policies: missing_owner, structure_drift,
  orphan_artifact, duplicate_implementation, deprecated_path_used enforcement.
- Git diff-based change detection (P2/P4); index the working tree, not a diff.
- Markdown/Trellis adapter facts inside inventory beyond what the index needs.
- Conflict detection logic beyond emitting an empty `conflicts: []`.
- No LLM similarity (plan §17).

## Acceptance Criteria

- [ ] `src/codas/structure/` exists with the loader(s) and index; registered as
      `active` in `.codas/structure.yml`.
- [ ] `codas inventory . --json` emits valid, deterministic Atlas JSON matching
      schema §5 (units with `observed.exists`/`observed.artifact_count`) plus
      program-plan facts; re-running yields byte-identical output.
- [ ] `structure_map_loads` runs inside `codas check`; a malformed
      `structure.yml` produces an error finding with path evidence.
- [ ] `codas check .` still passes (exit 0, 0 errors) on the current repo.
- [ ] New unit tests pass; bootstrap gate clean:
      `PYTHONPATH=src python3 -m unittest discover -s tests`.

## Notes

- Affected concepts: **Structure Map**, **Atlas Inventory**, **Program Plan**.
- Command name: `codas inventory` (plan §7 is command authority; schema §10's
  "codas structure" is older phrasing).
- Schema divergence to resolve in code: schema §5 ids use the unit key
  (`codas-core`); plan §6 example uses `structure-unit:<path>`. Follow schema §5
  (keyed id) since structure.yml is a keyed map — note the choice in the report.
- Determinism reminder: YAML dates load as `datetime.date` and break
  `json.dumps`; keep date fields as strings or stringify before serialize.
