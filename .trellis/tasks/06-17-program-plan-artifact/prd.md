# Define Codas Program Plan artifact

## Goal

Author `.codas/program.yml` as the repo-local Program Plan claim surface for
Codas, fixing the project-level roadmap (phases, work items, dependencies,
sequencing and exit criteria) above individual Trellis tasks. This closes the
gap where the roadmap only existed as prose in
`docs/codas-implementation-plan.html` with no governed, machine-readable
artifact.

## Background

- `docs/codas-implementation-plan.html` §8 defines phases P0–P7 with themes,
  deliverables and exit criteria. §6 defines the **Program Plan Work Item** data
  contract (`id`, `phase`, `title`, `depends_on`, `trellis_tasks`,
  `exit_criteria`). §12 places `program.yml` under `.codas/` as the authored
  Program Plan claim surface, parallel to `structure.yml`.
- The archived task `06-17-define-codas-program-plan-document-governance`
  defined the terminology (Program Plan, Project Document Set, Document Role
  Manifest, Document Steward) but explicitly deferred creating `.codas/program.yml`.
- This task creates the artifact; it does NOT implement a loader or validation.

## Requirements

- Create `.codas/program.yml` following the §6 Work Item contract: one work-item
  node per phase P0–P7, each with `id` (`program:P{n}:{slug}`), `phase`,
  `title`, `theme`, `depends_on`, `trellis_tasks`, `deliverables`,
  `exit_criteria`, `status`.
- Node content must be faithful to `implementation-plan.html` §8 (themes,
  deliverables, exit criteria), not invented. Where §6's example diverges from
  §8, §8 (the phase table) wins.
- Chain `depends_on` linearly P0→P7 (each phase depends on the prior), matching
  the plan's stated ordering.
- Map known Trellis tasks to nodes: P0 → `06-17-p0-codas-cli-core-self-check`;
  P1 → `06-17-design-codas-structure-map-schema` and this task.
- Mark P0 `status: completed`; P1 `status: in_progress` (foundation work next);
  P2–P7 `status: planned`.
- Register `.codas/program.yml` in `.codas/structure.yml` (new `program-plan`
  unit under `.codas`, added to `codas-config.allowed_children`), owner
  Document Steward.
- Add a `program.yml` pointer to `.codas/wiki/index.md` Canonical Sources.

## Non-Goals

- Do not implement a Program Plan loader, `codas plan`, or any validation
  (that is P1 code work).
- Do not author `.codas/documents.yml` (Document Role Manifest) — separate work.
- Do not decompose phases below work-item (per-phase) granularity yet.
- Do not change phase scope or ordering already fixed in
  `implementation-plan.html` §8.

## Acceptance Criteria

- [ ] `.codas/program.yml` exists, parses as valid YAML, and contains nodes
      `program:P0:cli-core` through `program:P7:*` per the §6 contract.
- [ ] Node themes/deliverables/exit_criteria match `implementation-plan.html` §8.
- [ ] `.codas/structure.yml` registers `program.yml` (unit + allowed_children),
      and `codas check .` passes (exit 0, no error findings).
- [ ] `.codas/wiki/index.md` references `program.yml`.
- [ ] Bootstrap gate clean: `PYTHONPATH=src python3 -m unittest discover -s tests`.

## Notes

- Affected concept: **Program Plan** (and its Document Steward owner).
- Canonical sources read before editing: `docs/codas-implementation-plan.html`
  (§6, §8, §12, §14, §17), `CONTEXT.md` (Program Plan terminology),
  `docs/codas-structure-map-schema.html` (authored-claim-surface pattern).
