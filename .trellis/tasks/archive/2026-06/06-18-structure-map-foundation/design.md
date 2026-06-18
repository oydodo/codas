# Design — P1 Structure Map and inventory foundation

## Module layout

Place loaders, models and index in the planned `codas-structure-module`
(`src/codas/structure/`); orchestrate the command in the existing `codas-app`
unit (`src/codas/app/`). This needs only flipping `codas-structure-module` to
`active` in `.codas/structure.yml` — no new structure units.

```
src/codas/structure/
  __init__.py
  models.py          # typed dataclasses (StructureMap, StructureUnit, ProgramPlan, WorkItem, ...)
  loader.py          # load_structure_map(path) -> StructureMap; raises StructureMapError
  program_loader.py  # load_program_plan(path) -> ProgramPlan; raises ProgramPlanError
  index.py           # build_artifact_index(repo, roots, structure_map) -> ArtifactIndex
  inventory.py       # build_inventory(repo, config) -> dict  (normalized atlas JSON)
src/codas/app/
  inventory.py       # run_inventory(repo) -> (report_obj); CLI orchestration, mirrors app/check.py
src/codas/policies/
  structure_map.py   # check_structure_map(repo, config) -> list[Finding]  (structure_map_loads)
```

Deviation noted: plan §5 lists a separate `Program` module. For this slice the
Program Plan loader co-locates under `structure/` to avoid adding a structure
unit; a dedicated `src/codas/program/` can be split out later.

## Models (`structure/models.py`)

Frozen dataclasses; collections as tuples so models are hashable/immutable.

```python
@dataclass(frozen=True)
class StructureUnit:
    id: str                  # keyed name, e.g. "codas-core"
    path: str
    kind: str
    owner: str
    purpose: str
    canonical_placement: str
    status: str = "active"
    allowed_children: tuple[str, ...] = ()
    must_update_if_changed: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

@dataclass(frozen=True)
class DependencyRule:
    unit: str
    may_depend_on: tuple[str, ...] = ()
    must_not_depend_on: tuple[str, ...] = ()

@dataclass(frozen=True)
class DeprecatedPath:
    id: str
    path: str
    status: str
    replacement: str | None = None
    reason: str | None = None

@dataclass(frozen=True)
class StructureMap:
    version: int
    kind: str
    units: tuple[StructureUnit, ...]            # authored order preserved
    dependency_rules: tuple[DependencyRule, ...]
    deprecated_paths: tuple[DeprecatedPath, ...]
    source: str                                 # ".codas/structure.yml" (repo-relative)
    metadata: Mapping[str, object] = field(default_factory=dict)   # raw, preserved
    defaults: Mapping[str, object] = field(default_factory=dict)   # raw; defaults.status applied at normalize
    roles: Mapping[str, str] = field(default_factory=dict)         # raw role-key -> display name

@dataclass(frozen=True)
class WorkItem:
    id: str                  # "program:P1:structure-map-foundation"
    phase: str
    title: str
    status: str
    depends_on: tuple[str, ...] = ()
    trellis_tasks: tuple[str, ...] = ()
    theme: str = ""
    deliverables: tuple[str, ...] = ()
    exit_criteria: tuple[str, ...] = ()

@dataclass(frozen=True)
class ProgramPlan:
    version: int
    kind: str
    work_items: tuple[WorkItem, ...]
    source: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    defaults: Mapping[str, object] = field(default_factory=dict)
```

## Structure loader (`structure/loader.py`)

`load_structure_map(path: Path) -> StructureMap`. Raises `StructureMapError`
(message + repo-relative path) on any failure below. This maps directly to the
schema §8 `structure_map_loads` policy.

Validation (per schema §3/§4):
1. File exists and parses as a YAML mapping.
2. Top-level has `version` (int), `kind == "structure_map"`, non-empty `units`
   mapping.
3. Each unit has non-empty required fields: `path`, `kind`, `owner`, `purpose`,
   `canonical_placement`.
4. `status`, when present, in `{active, planned, deprecated, removed, external}`
   (default from `defaults.status`, else `active`).
5. Every `allowed_children` id resolves to a defined unit.
6. Every `dependency_rules.<unit>` key and its `may_depend_on` /
   `must_not_depend_on` targets resolve to defined units.
7. Each `deprecated_paths.<id>` has a `path`.

Reference-integrity failures (5–7) are part of "the map is well-formed" and
raise `StructureMapError` too (one policy id, clear message naming the offending
id). Unit order is the authored YAML order (pyyaml preserves insertion order).

## Program loader (`structure/program_loader.py`)

`load_program_plan(path) -> ProgramPlan`. Raises `ProgramPlanError`.
1. Parses; has `version`, `kind == "program_plan"`, `work_items` list.
2. Each item: `id` matches `^program:P\d+:[a-z0-9-]+$`, has `phase`, `title`,
   `status`.
3. Every `depends_on` id resolves to a defined work-item id.
4. Dependency graph is acyclic (DFS; raise on back-edge naming the cycle).

## Artifact index (`structure/index.py`)

`build_artifact_index(repo, roots, structure_map) -> ArtifactIndex`.

- File discovery: `git -C <repo> ls-files --cached --others --exclude-standard`
  → tracked + untracked-but-not-ignored files. Deterministic, respects
  `.gitignore` for free. Fallback (non-git repo): `os.walk` skipping `.git`,
  `__pycache__`, `*.pyc`. Restrict to files under `config.workspace.roots`
  (default `["."]`).
- Path normalization: every `unit.path` and every git path is normalized to a
  repo-relative, forward-slash, no-leading-`./` form. The root unit `path: "."`
  normalizes to the empty prefix `""`.
- Mapping (literal-path units): the owning unit is the one whose normalized
  `path` is the **longest** prefix of the file. Prefix test: `prefix == ""`
  (root unit, matches everything) OR `file == prefix` (a file-path unit such as
  `agents-guide` → `AGENTS.md`) OR `file.startswith(prefix + "/")`. Longest
  prefix wins; the `""` root is least-specific so every deeper unit beats it.
  Files matching no unit are `unowned` (collected for future orphan_artifact;
  not a finding this slice). With the root unit present, `unowned` is normally
  empty — the root catches the remainder.
- Mapping (glob-path units): if `unit.path` contains glob metacharacters
  (`* ? [`), match files via `fnmatch`; `exists` = at least one match. Ordering
  specificity uses the literal prefix before the first metacharacter; full glob
  vs literal precedence is a documented limitation (no glob units exist in the
  current map). `Path.exists()` is only used for literal-path units.
- Per unit: `exists` = `unit.path` exists on disk (root `.` → repo exists =
  `true`); `artifact_count` = number of indexed files matched by this unit's
  normalized prefix (inclusive subtree — matches schema §5 example where
  `codas-core`=`src/codas` counts the src/codas subtree; that subtree is 16
  files now, 14 when the schema example was authored). Subtree counts
  intentionally overlap between parent and child units; the root unit's count
  equals the total indexed file count.

## Inventory (`structure/inventory.py` + `app/inventory.py`)

`build_inventory(repo, config) -> dict`. The structure portion keeps the schema
§5 contract **flat at the top level** (`schema_version`, `source`, `units`,
`conflicts`) so it is a drop-in for `.codas/inventory/structure.json`; the
program facts are added as a sibling `program` key (its own `source`). This is
the combined `codas inventory` output; a future split can write `structure.json`
(top-level §5 object minus `program`) and an aggregate `atlas.json` unchanged.

```json
{
  "schema_version": 1,
  "source": ".codas/structure.yml",
  "units": [
    {
      "id": "codas-core",
      "path": "src/codas",
      "kind": "package",
      "owner": "Codas Core",
      "status": "active",
      "claims": ["claim:structure:codas-core:canonical_placement"],
      "observed": {"exists": true, "artifact_count": 16},
      "must_update_if_changed": ["docs/codas-implementation-plan.html"]
    }
  ],
  "conflicts": [],
  "program": {
    "source": ".codas/program.yml",
    "work_items": [
      {"id": "program:P0:cli-core", "phase": "P0", "status": "completed",
       "depends_on": [], "trellis_tasks": ["06-17-p0-codas-cli-core-self-check"]}
    ]
  }
}
```

- `claims`: one derived id per unit, `claim:structure:<id>:canonical_placement`
  (matches §5 example). Deterministic, no I/O.
- `conflicts`: always `[]` this slice (detection deferred).
- Determinism: units sorted by `id`, work_items by `id`; `json.dumps(obj,
  indent=2, sort_keys=True)`; no timestamps, hashes or wall-clock. Re-run →
  byte-identical.

CLI: `codas inventory [repo] [--json]`. `--json` prints the JSON; default prints
a short human summary (unit count, total artifacts, unowned count, phase
counts). Replaces the P0 `parser.error(...)` stub in `cli.py`.

## check wiring (`policies/structure_map.py`)

`check_structure_map(repo, config) -> list[Finding]`: call
`load_structure_map`; on `StructureMapError` return one `error` finding
(`check_id="structure-map-loads"`, evidence = `.codas/structure.yml`); else `[]`.
Append to `run_check` in `app/check.py` after the existing bootstrap policies.
The current repo's `structure.yml` must pass (verify before finishing).

## Tests (`tests/`)

- `test_structure_loader.py`: valid repo map loads (unit count, fields);
  malformed cases each raise `StructureMapError` — missing `version`, missing
  unit `owner`, dangling `allowed_children`, bad `status`.
- `test_program_loader.py`: valid load; dangling `depends_on` raises; cyclic
  graph raises.
- `test_artifact_index.py`: temp tree → files map to deepest unit; a
  `.gitignore`'d file is excluded.
- `test_inventory.py`: `build_inventory` twice → identical `json.dumps`;
  structure units present with `observed`; program work_items present.
- `test_check_structure_map.py`: malformed `structure.yml` → one error finding.
- Existing 5 tests stay green.

## Open choices (resolved)

- Command name `codas inventory` (plan §7 authority), not `codas structure`.
- Unit `id` = authored key (`codas-core`), per schema §5, not plan §6's
  `structure-unit:<path>`.
- `artifact_count` = inclusive subtree count (matches §5 example).
- Reference-integrity failures raise under the single `structure_map_loads`
  policy rather than a separate policy id this slice.

## YAML parsing decision

The repo adopted **PyYAML** (`yaml.safe_load`) for all `.codas/*.yml` parsing
(commit `6e1b43c`), replacing the hand-rolled `parse_simple_yaml`. The custom
parser could not handle block scalars and mis-parsed colon-bearing list items
(e.g. `program.yml` `depends_on`) as inline mappings. The structure/program
loaders reuse `config.loader.load_yaml_mapping`, which is now PyYAML-backed.

## Codex-review fixes folded in

- **§5 contract stays flat** at top level (`schema_version`/`source`/`units`/
  `conflicts`); `program` is a sibling key, not a wrapper. (was BLOCKER)
- **No silent data loss**: `StructureMap` retains `metadata`/`defaults`/`roles`;
  `WorkItem` retains `theme`/`deliverables`/`exit_criteria`; `ProgramPlan`
  retains `metadata`/`defaults` (raw mappings/tuples, preserved even if the
  inventory output emits a subset). (was MAJOR)
- **Root unit `path: "."`** normalizes to empty prefix and is the least-specific
  owner — fixes `README.md`/`pyproject.toml` etc. being orphaned. Verified:
  `"README.md".startswith("./")` is `False`, so the naive rule was broken. (was
  MAJOR)
- **Glob unit paths** handled via `fnmatch` with a documented specificity
  limitation; no glob units exist in the current map. (was MINOR)
