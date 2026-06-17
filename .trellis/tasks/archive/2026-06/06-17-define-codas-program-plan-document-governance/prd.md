# Define Codas Program Plan and Document Governance

## Problem

Trellis gives Codas a task-level workflow, but Codas still lacks a project-level
planning and document-governance layer. Without that layer, design docs,
implementation plans, roadmap docs, specs, wiki pages and Trellis tasks can
drift independently while each individual task still appears locally clean.

Recent draft edits introduced Program Plan and document-governance terminology
into `CONTEXT.md`, `docs/codas-design.html` and
`docs/codas-implementation-plan.html`. Those edits need their own Trellis task
instead of being tracked under the Structure Map schema task.

## Goal

Define the Codas project planning and document-governance model, and track the
existing draft edits under a dedicated Trellis task before any further design or
implementation work continues.

## Requirements

- Define Program Plan / Implementation Roadmap as the project-level roadmap
  above individual Trellis tasks.
- Define Project Document Set as the expected governance and planning document
  set for a governed repository.
- Define Document Role Manifest as the repo-local mapping from document roles
  to concrete files, owners, authority and update triggers.
- Define Document Role as the responsibility a governance or planning document
  serves independently from its concrete path or format.
- Define Document Steward as the Domain Role responsible for maintaining the
  Project Document Set and Document Role Manifest.
- Explain the relationship between:
  - product / architecture design documents,
  - implementation plans,
  - Program Plan / roadmap artifacts,
  - Structure Map,
  - Trellis task PRDs and context,
  - Trellis specs,
  - Atlas Wiki orientation pages.
- Keep Trellis as the task-level workflow, not the project-level roadmap
  authority.
- Record that existing draft edits in `CONTEXT.md`, `docs/codas-design.html`
  and `docs/codas-implementation-plan.html` belong to this task.

## Non-Goals

- Do not implement `codas plan` in this task.
- Do not implement Program Plan validation in this task.
- Do not create finalized schemas for `.codas/program.yml` or
  `.codas/documents.yml` in this task.
- Do not continue Structure Map schema design in this task.

## Acceptance Criteria

- `CONTEXT.md` contains accepted terminology for Program Plan, Project Document
  Set, Document Role, Document Role Manifest and Document Steward.
- `docs/codas-design.html` explains Program Plan and project planning document
  roles at the product-design level.
- `docs/codas-implementation-plan.html` identifies future Program and Documents
  modules, data contracts and policies at the implementation-plan level.
- The task context records all files touched by the draft document-governance
  edits.
- Trellis validation status is known and any unresolved validation failure is
  explained instead of hidden.
