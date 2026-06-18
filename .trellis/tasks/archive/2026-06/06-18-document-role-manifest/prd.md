# P1 Document Role Manifest and document_set_complete

## Goal

Complete the P1 document-governance foundation: author `.codas/documents.yml`
(the Document Role Manifest binding document roles to concrete files), load and
validate it, verify the Project Document Set via a `document_set_complete`
policy, and surface document-role facts in `codas inventory`. This is the last
loader-and-claim-surface piece of P1, mirroring the Structure Map and Program
Plan work already shipped.

## Authoritative sources

- `docs/codas-implementation-plan.html` — §5 Documents module ("Load the
  Document Role Manifest and verify the Project Document Set exists with declared
  authority, owners and update triggers"; P1), §6 Document Role Manifest Entry
  contract, §10 policy roadmap (`document_set_complete`: required Document Roles
  resolve to existing files with authority, owner and update triggers).
- `CONTEXT.md` — Project Document Set, Document Role, Document Role Manifest,
  Document Steward terms.

## Document Role Manifest Entry contract (§6)

```
role:        e.g. implementation_plan       (keyed id)
path:        docs/codas-implementation-plan.html
authority:   authoritative | supporting
owner:       Document Steward (a role/team/boundary)
updates_when: [ module_boundaries_change, phase_order_changes, ... ]
```

## Scope (this task)

1. **Author `.codas/documents.yml`** — the Document Role Manifest for this repo.
   Cover the real Project Document Set: product design, implementation plan,
   structure-map schema, structure map, program plan, policy set, config,
   waivers, orientation index, README, domain context, agent instructions,
   workflow. Each entry: `role`, `path`, `authority`, `owner`, `updates_when`.
2. **Documents loader** — parse + validate `.codas/documents.yml`: required
   `version`, `kind`, `documents` map; each entry has `role` (implicit key),
   `path`, `authority` in `{authoritative, supporting}`, `owner`,
   non-empty `updates_when` list. Raise a typed error → `document_set_complete`
   finding on malformed input.
3. **`document_set_complete` policy** — wire into `codas check`: each declared
   role's `path` must exist on disk; malformed manifest or a missing target file
   yields an error finding with path evidence.
4. **Inventory facts** — add a `documents` sibling block to the `codas inventory`
   JSON (role/path/authority/owner/exists), deterministic.
5. **Register** `.codas/documents.yml` in `.codas/structure.yml` (new
   `document-manifest` unit under `.codas`, owner Document Steward) + add to
   `config.yml` authoritative sources + reference in `.codas/wiki/index.md`.
6. **Tests** — loader (valid + each validation failure), `document_set_complete`
   policy (missing target file → finding; valid repo → none), inventory contains
   the documents block.

## Non-Goals (defer)

- Staleness / update-trigger enforcement (only existence + shape this slice;
  §10 "Later Expansion" defers staleness checks).
- Doc claim index and Trellis task facts (separate P1 items).
- P2 substantive structure policies.
- No LLM similarity (plan §17).

## Acceptance Criteria

- [ ] `.codas/documents.yml` exists, parses, and lists the repo's Project
      Document Set with role/path/authority/owner/updates_when per §6.
- [ ] Documents loader is implemented with validation; malformed manifest raises
      a typed error surfaced as a `document_set_complete` error finding.
- [ ] `document_set_complete` runs in `codas check`; a declared role pointing at
      a missing file yields an error finding with path evidence.
- [ ] `codas inventory . --json` includes a deterministic `documents` block.
- [ ] `codas check .` passes (exit 0, 0 errors); bootstrap gate clean.
- [ ] New unit tests pass.

## Notes

- Affected concepts: **Document Role Manifest**, **Project Document Set**,
  **Document Role**, owned by **Document Steward**.
- Co-locate the loader under `src/codas/structure/` alongside the structure and
  program loaders (deviation from plan §5's separate Documents module, same as
  the Program Plan loader; a split can come later).
