# Trellis Task System

## Canonical Definition

Codas uses Trellis as its project task system. Trellis is responsible for task
lifecycle, persisted requirements, task context and session workflow.

Evidence:

- `.trellis/workflow.md`
- `.trellis/config.yaml`
- `.trellis/spec/codas/workflow/task-system.md`
- `.codas/config.yml`

## Boundary

Trellis owns:

- task creation and lifecycle
- `prd.md` requirements
- `implement.jsonl` and `check.jsonl` context
- workflow phase guidance

Codas owns:

- architecture inventory
- fact and claim stores
- concept index
- policy gates
- waivers
- Atlas Wiki
- constraint conflict detection

## Required Synchronization

When task workflow, task metadata, Trellis context files or workflow adapter
behavior changes, update:

- `.trellis/workflow.md`
- `.trellis/spec/codas/workflow/task-system.md`
- `.codas/config.yml`
- `docs/codas-design.html`
