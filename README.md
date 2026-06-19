# Codas

Codas is a Code Atlas System for coding agents. It is being built as a
CLI-first, agent-agnostic governance layer for repositories that coding agents
maintain over time.

The formal Codas design lives in `docs/codas-design.html`.
The implementation plan lives in `docs/codas-implementation-plan.html`.
The Structure Map schema lives in `docs/codas-structure-map-schema.html`.

## Dogfooding

This repository is the first Codas-governed workspace: `codas check .` runs the
full policy set here and stays green. Agents working here also follow the
bootstrap gate in `.codas/config.yml` and `.codas/wiki/index.md`:

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

Build the normalized Atlas inventory (Structure Map units mapped to repository
artifacts, plus Program Plan facts):

```bash
PYTHONPATH=src python3 -m codas inventory .
PYTHONPATH=src python3 -m codas inventory . --json
```

The `--json` output follows the Structure Map schema's normalized JSON shape and
is deterministic for a given repository state.

Assemble the read-first context pack for a task:

```bash
PYTHONPATH=src python3 -m codas preflight . --task <id>
```

## Atlas Wiki

Atlas is Codas's **live governance map**, not a post-hoc documentation generator.
Where a tool like CodeWiki or DeepWiki describes a finished codebase for human
readers, Atlas serves **agents and humans during development**: it guides an agent
before it edits (what to read, where new code belongs, what it may depend on) and
lets a human track plan progress and control deviation. It is prescriptive and
**verified** — every wiki claim is checked against repository facts
(`stale_wiki_claim`, and the planned `generated_wiki_drift`), and the correctness
core stays deterministic and LLM-free. Codas can also emit a verified **grounding
pack** that an external LLM-wiki generator consumes to produce an optional
human-prose doc-site, whose output Codas then verifies. The architecture decision
is recorded in `.trellis/tasks/06-19-wiki-architecture`.

## Status

P0–P4 are complete: the `codas` package and CLI; config / structure-map /
program-plan / document-manifest loaders; a deterministic Atlas **inventory**
(`codas inventory --json`); 15 wired governance **policies** (`codas check`,
currently zero findings on this repo); a **preflight** context pack; and run
**provenance** plus a **receipt** ledger (`codas check --json` / `--receipt`). P5
(wiki reconciliation) is in progress. Swift/Ciri-specific prototype code was
removed; ecosystem-specific extraction lives behind adapters.
