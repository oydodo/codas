# Codas Task System

## Canonical Task System

Codas uses Trellis as its project task system.

Implementation work must be represented by a task under `.trellis/tasks/`.
Each task should contain:

- `task.json`: machine-readable task metadata.
- `prd.md`: persisted requirements and acceptance criteria.
- `implement.jsonl`: implementation context.
- `check.jsonl`: verification context.
- `research/`: optional durable research artifacts.
- `info.md`: optional technical design notes.

## Agent Requirements

- Do not leave task intent only in chat.
- Create or update the Trellis task before substantial implementation.
- Keep `prd.md` synchronized when the user's requirements change.
- Add Codas design, wiki, policy and relevant spec files to task context when they affect the work.
- Use a dedicated Trellis task for cross-cutting governance changes such as Program Plan, document governance, role terminology or workflow policy. Do not hide those changes inside a nearby feature, schema or implementation task.
- Finish a task only after local verification has run and findings are resolved or explicitly waived.

## Relationship to Codas

Trellis is the workflow adapter and task fact source for this repository.
Codas remains responsible for architecture inventory, policy gates, wiki and
constraint conflict detection.

Trellis answers:

- What task are we doing?
- What requirements were persisted?
- What context was injected for implementation and review?

Codas answers:

- What repository facts exist?
- What canonical implementation or owner applies?
- What policies did the change violate?
- Which claims drifted or conflicted?

## Evidence

- `.trellis/workflow.md`
- `.trellis/config.yaml`
- `.codas/config.yml`
- `docs/codas-design.html`
