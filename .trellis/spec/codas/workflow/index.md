# Codas Workflow Spec Index

## Pre-Development Checklist

- Read `docs/codas-design.html` before changing Codas architecture, command shape, policy semantics or data model.
- Read `.codas/wiki/index.md` before adding new concepts or implementation areas.
- Use Trellis as the task system: create or update a task under `.trellis/tasks/` for implementation work.
- Update Codas claims when behavior, architecture, policy or workflow changes.
- Run the bootstrap gate before reporting completion.

## Guidelines

- [Task System](task-system.md)

## Quality Check

- The task has a Trellis record with `prd.md`.
- Relevant implementation/check context files exist when code or docs are changed.
- New artifacts have an owner and purpose.
- Codas design/wiki/config claims are synchronized with the change.
- Bootstrap gate passes:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
git status --short
```
