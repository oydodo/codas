# Design — P1 Document Role Manifest and document_set_complete

Mirrors the shipped Structure Map / Program Plan loaders (commit 413c50f), their
PyYAML + dup-key parsing, and the check wiring. Revised after codex review of v1.

## Authored `.codas/documents.yml`

Keyed map of document roles → entry (§6 contract) plus a top-level
`required_roles` list (the roles a governed Codas repo must declare). Authorities
are reconciled with `config.yml` `constraint_sources` (see Reconciliation).

```yaml
version: 1
kind: document_role_manifest
metadata:
  project: Codas
  owner: Document Steward
  updated: "2026-06-18"
defaults:
  authority: authoritative
required_roles:
  - product_design
  - implementation_plan
  - structure_map_schema
  - structure_map
  - program_plan
  - policy_set
  - config
  - waivers
  - domain_context
  - workflow
documents:
  product_design:
    path: docs/codas-design.html
    authority: authoritative
    owner: Codas Core
    updates_when: [product_scope_changes, architecture_changes]
  implementation_plan:
    path: docs/codas-implementation-plan.html
    authority: authoritative
    owner: Document Steward
    updates_when: [module_boundaries_change, phase_order_changes, policy_roadmap_changes]
  structure_map_schema:
    path: docs/codas-structure-map-schema.html
    authority: authoritative
    owner: Structure Architect
    updates_when: [structure_map_fields_change, validation_behavior_changes]
  structure_map:
    path: .codas/structure.yml
    authority: authoritative
    owner: Structure Steward
    updates_when: [units_change, ownership_changes, deprecated_paths_change]
  program_plan:
    path: .codas/program.yml
    authority: authoritative
    owner: Document Steward
    updates_when: [phase_status_changes, work_item_added, dependencies_change]
  policy_set:
    path: .codas/policies.yml
    authority: authoritative
    owner: Policy Maintainer
    updates_when: [policy_added, severity_changes]
  config:
    path: .codas/config.yml
    authority: authoritative
    owner: Policy Maintainer
    updates_when: [sources_change, workflow_adapter_changes]
  waivers:
    path: .codas/waivers.yml
    authority: authoritative
    owner: Policy Maintainer
    updates_when: [waiver_added, waiver_expires]
  domain_context:
    path: CONTEXT.md
    authority: authoritative
    owner: Document Steward
    updates_when: [terminology_changes, new_concept_defined]
  workflow:
    path: .trellis/workflow.md
    authority: authoritative
    owner: Task Steward
    updates_when: [workflow_phases_change]
  task_system_config:
    path: .trellis/config.yaml
    authority: authoritative
    owner: Task Steward
    updates_when: [packages_change, hooks_change]
  orientation_index:
    path: .codas/wiki/index.md
    authority: supporting
    owner: Orientation Curator
    updates_when: [concept_added, canonical_source_changes]
  readme:
    path: README.md
    authority: supporting
    owner: Codas Core
    updates_when: [usage_changes, commands_change]
  agent_instructions:
    path: AGENTS.md
    authority: supporting
    owner: Task Steward
    updates_when: [trellis_update]
```

### Coverage rule

Each role maps to exactly one file (§6). Multi-file governance areas are
represented by an index/parent role, not per-file roles: `.trellis/spec/**/*.md`
is covered by config's authoritative glob and the `workflow` role; the Atlas
Wiki concept pages are covered by `orientation_index`. This is a deliberate
1-role-1-file stance, noted so the omission of per-spec / per-concept roles is
explicit, not accidental.

## Models (`structure/models.py`, appended)

```python
@dataclass(frozen=True)
class DocumentRole:
    role: str                 # keyed id
    path: str
    authority: str            # authoritative | supporting
    owner: str
    updates_when: tuple[str, ...] = ()

@dataclass(frozen=True)
class DocumentManifest:
    version: int
    kind: str
    documents: tuple[DocumentRole, ...]
    required_roles: tuple[str, ...] = ()
    source: str = ".codas/documents.yml"
    metadata: Mapping[str, object] = field(default_factory=dict)
    defaults: Mapping[str, object] = field(default_factory=dict)

    def role_ids(self) -> frozenset[str]:
        return frozenset(d.role for d in self.documents)
```

## Loader (`structure/document_loader.py`)

`load_document_manifest(path, source=None) -> DocumentManifest`. Raises
`DocumentManifestError`, reuses `load_yaml_mapping`. Validation:
1. `version` int; `kind == "document_role_manifest"`; non-empty `documents` map.
2. Each entry: `path` non-empty str; `authority` (entry or `defaults.authority`)
   in `{authoritative, supporting}`; `owner` non-empty str; `updates_when` is a
   **non-empty list of non-empty strings** (per PRD / §10 "update triggers").
3. `required_roles` (if present) is a list of strings; every id must resolve to
   a declared document (else error — a required role is undeclared).

## Policy (`policies/document_set.py`)

`check_document_set(repo, config) -> list[Finding]`, wired into `run_check`
after `check_program_plan`. `check_id="document-set-complete"`.
- Missing `.codas/documents.yml` → `[]` (covered by check_config_sources).
- `DocumentManifestError` → one error finding.
- Each `required_roles` id not declared → error finding (missing required role).
- Each declared role whose `path` does not exist on disk → error finding (path
  evidence, message names the role).
- **Authority reconciliation**: for each role whose `path` is listed verbatim in
  `config.yml` `constraint_sources`, the manifest `authority` must match the
  config classification (authoritative vs supporting). Mismatch → error finding
  (this is the constraint_conflict case Codas exists to catch). Files matched
  only by a glob, or absent from config, are not cross-checked.

## config.yml reconciliation (close the gap)

config currently omits four governance files the manifest governs. Add them so
config and the manifest agree (and the authority cross-check passes):
- authoritative: `.codas/waivers.yml`, `CONTEXT.md`
- supporting: `.codas/wiki/index.md`, `AGENTS.md`

(`.trellis/config.yaml` and `.trellis/workflow.md` are already authoritative in
config; README already supporting — manifest matches.)

## Inventory (`structure/inventory.py`, extended)

Add a sibling `documents` block (parallel to `program`), only when the file
exists; deterministic (roles sorted by id):

```json
"documents": {
  "source": ".codas/documents.yml",
  "roles": [
    {"role": "implementation_plan", "path": "docs/codas-implementation-plan.html",
     "authority": "authoritative", "owner": "Document Steward",
     "observed": {"exists": true}}
  ]
}
```

`exists` = `(repo / path).exists()`. No date emitted; §5 top-level keys untouched.

## Registration

- `structure.yml`: new `document-manifest` unit (`path: .codas/documents.yml`,
  kind `document_role_manifest`, owner `Document Steward`, must_update_if_changed
  → implementation-plan + wiki); add to `codas-config.allowed_children`.
- `config.yml`: add `.codas/documents.yml` to authoritative + the four
  reconciliation entries above.
- `.codas/wiki/index.md`: add a pointer.

## Tests (`tests/test_document_loader.py` + inventory/policy)

- loader: valid manifest loads (role count, fields, `defaults.authority`
  applied); failures raise — missing version, bad kind, entry missing path, bad
  authority value, missing owner, **empty/missing `updates_when`**, **non-string
  trigger**, **required_role not declared**.
- `document_set_complete`: required role missing → finding; declared role with a
  missing target file → finding; **authority mismatch vs config → finding**; the
  real repo manifest → no findings.
- inventory: `documents` block present, deterministic, `exists` true for real
  paths.

## Resolved choices

- `required_roles` is a top-level manifest field (data-driven), not hardcoded in
  the policy; document_set_complete enforces presence + path existence.
- `updates_when` must be non-empty.
- Authority is reconciled with `config.yml` via cross-check; the four gap files
  are added to config so the surfaces agree.
- Loader co-located under `structure/` with the other governance loaders.
