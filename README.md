# Codas

Codas is a Code Atlas System for coding agents. It is being built as a
CLI-first, agent-agnostic governance layer for repositories that coding agents
maintain over time.

The formal Codas design lives in `docs/codas-design.html`.
The implementation plan lives in `docs/codas-implementation-plan.html`.
The Structure Map schema lives in `docs/codas-structure-map-schema.html`.

## Dogfooding

This repository is the first Codas-governed workspace. Until the `codas` CLI can
enforce its own rules, agents working here follow the bootstrap protocol in
`.codas/config.yml` and `.codas/wiki/index.md`:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
git status --short
```

Every implementation task should name the affected concept before editing,
read the canonical design/wiki sources, update related claims when behavior or
architecture changes, and explain any new artifact in the final report.

## Task System

Codas uses Trellis as its project task system. Implementation work should have a
task under `.trellis/tasks/` with persisted requirements in `prd.md` and
implementation/check context in `implement.jsonl` and `check.jsonl`.

Create a task with:

```bash
python3 ./.trellis/scripts/task.py create "<title>" --slug <slug> --assignee <name>
python3 ./.trellis/scripts/task.py add-context <task-dir> implement <path> "<reason>"
python3 ./.trellis/scripts/task.py start <task-dir>
```

`implement.jsonl` / `check.jsonl` are seeded on `task.py create` and curated with
`task.py add-context` during planning. The old `init-context` subcommand was
removed in Trellis v0.5.0-beta.12.

Trellis manages task workflow; Codas manages repository facts, policies, wiki,
waivers and architecture gates.

## Usage

Run the Codas self-check:

```bash
PYTHONPATH=src python3 -m codas check .
```

Emit machine-readable output:

```bash
PYTHONPATH=src python3 -m codas check . --json
```

Use the local wrapper:

```bash
python3 scripts/codas check .
```

The CLI exits non-zero when it finds an `error`.

## Current P0 Scope

P0 implements the Codas package, CLI, config loader and first self-check
policies for this repository. Swift/Ciri-specific prototype code has been
removed; future ecosystem-specific checks must be implemented through adapters.
