# Repository Structure

## Canonical Definition

Repository Structure is the intentional organization of files, directories,
module boundaries, ownership and canonical placement inside a repository. In
Codas, the authored carrier for these claims is the Structure Map at
`.codas/structure.yml`.

Evidence:

- `CONTEXT.md`
- `docs/codas-structure-map-schema.html`
- `.codas/structure.yml`

## Boundary

The repository itself remains the source of Observed Facts. The Structure Map
contains authored Claims about how the repository should be organized. Codas
must reconcile those Claims against repository facts before using them as
Governance Facts.

Atlas Wiki can orient agents inside the Repository Structure, but it must not
override `.codas/structure.yml` or observed repository facts.

## Domain Roles

- Structure Architect initializes the Structure Map near project start.
- Structure Steward maintains the Structure Map during project execution.
- Orientation Curator keeps this Atlas Wiki navigation aligned with the map.
- Policy Maintainer turns structure expectations into executable policies.

## Current Codas Map

The current Codas Structure Map covers:

- `.codas/` governance state
- `.codas/wiki/` Orientation Layer
- `docs/` product, implementation and schema documents
- `src/codas/` runtime implementation
- `tests/` verification
- `scripts/` command wrappers
- `.trellis/` task-system workflow and task context

It also marks legacy `harness_guard` paths as removed and replaced by Codas
paths.

Evidence:

- `.codas/structure.yml`

## Required Synchronization

When Repository Structure, Structure Map fields, structure policies or role
workflows change, update:

- `.codas/structure.yml`
- `docs/codas-structure-map-schema.html`
- `docs/codas-implementation-plan.html`
- `docs/codas-design.html`
- `.codas/wiki/index.md`
- this concept page
