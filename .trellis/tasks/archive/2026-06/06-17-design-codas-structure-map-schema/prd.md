# Design Codas Structure Map Schema

## Problem

Codas has resolved the terminology for Repository Structure and Structure Map,
but the repo does not yet define the concrete schema that a Structure Architect
would initialize or a Structure Steward would maintain. Without that carrier,
structure governance remains a document idea and agents can still create
duplicate implementation paths, orphan artifacts or unclear ownership.

## Goal

Design the first Structure Map schema and dogfood it in the Codas repository.
The output should make Repository Structure claims explicit, reviewable and
ready for later Codas validation.

## Requirements

- Define the purpose, authority and non-goals of the Structure Map.
- Specify the authored form under `.codas/structure.yml`.
- Specify the future normalized form under `.codas/inventory/structure.json`.
- Define required fields for structure units, ownership, canonical placement,
  update obligations and dependency boundaries.
- Define the Structure Architect and Structure Steward workflows against the
  schema.
- Add a first Codas repository Structure Map that covers the current top-level
  areas and important implementation paths.
- Add Atlas Wiki navigation for Repository Structure / Structure Map.
- Keep the schema language-agnostic and agent-agnostic.

## Non-Goals

- Do not implement the full `codas structure` command in this task.
- Do not implement a full policy engine for structure drift in this task.
- Do not define Program Plan, Project Document Set, Document Role Manifest or
  Document Steward in this task. Those belong to
  `06-17-define-codas-program-plan-document-governance`.
- Do not add language-specific parsing rules to the core schema.
- Do not treat Atlas Wiki as the source of structure facts.

## Acceptance Criteria

- `docs/codas-structure-map-schema.html` explains the Structure Map schema,
  workflows, validation model and examples.
- `.codas/structure.yml` exists as the first dogfooded map for this repository.
- `.codas/config.yml` lists the Structure Map and schema doc as authoritative
  constraint sources.
- `.codas/wiki/index.md` links to a Repository Structure concept page.
- `.codas/wiki/concepts/repository-structure.md` explains the concept, evidence
  and required synchronization.
- `docs/codas-design.html` and `docs/codas-implementation-plan.html` point to
  the schema as the detailed structure contract.
- Trellis task context validates.
- `codas check`, unit tests and bootstrap gate pass.
