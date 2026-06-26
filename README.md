# Codas

Codas is a Code Atlas System for coding agents. It is being built as a
CLI-first, agent-agnostic governance layer for repositories that coding agents
maintain over time.

The formal Codas design lives in `docs/codas-design.html`.
The implementation plan lives in `docs/codas-implementation-plan.html`.
The Structure Map schema lives in `docs/codas-structure-map-schema.html`.

## Install

Codas is a CLI you install once and use across repositories — the governance
state lives per-repo in `.codas/`. Requires Python 3.9+.

```bash
pipx install codas        # isolated, recommended; or: pip install codas
```

From a source checkout or GitHub URL before a registry release:

```bash
pipx install .
pip install -e .
```

Then, in a repository you want Codas to govern:

```bash
codas init                # scaffold a minimal .codas/ skeleton
codas hooks --install     # install the git gate + agent-injection hooks
codas check .             # run the policy gate
```

A terminal-state `npx codas` (an npm wrapper over a prebuilt binary, for the
Node-centric agent-coding ecosystem) is planned; today pip/pipx is the install path.

> The `PYTHONPATH=src python3 -m codas …` form used elsewhere in this README is for a
> **source checkout** (developing Codas itself / dogfooding this repo), where Codas is
> not on `PATH`. An installed `codas` needs no `PYTHONPATH`.

## Repository Layout

Codas uses the standard Python `src/` layout. Product code lives under
`src/codas/`; tests live under `tests/`; governance state lives under `.codas/`;
Trellis task state lives under `.trellis/`; generated Atlas book pages live under
`wiki/`. Build outputs, bytecode caches, egg-info metadata, local CodeGraph data,
and machine-local settings are ignored and should not be committed.

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

Work with the Atlas wiki spine — emit the verified grounding pack, render the
committed generated sections, and gate their freshness:

```bash
PYTHONPATH=src python3 -m codas wiki . --emit-pack
PYTHONPATH=src python3 -m codas wiki . --write
PYTHONPATH=src python3 -m codas wiki . --verify
```

`--emit-pack` emits the verified grounding pack, `--write` renders the committed
generated sections, and `--verify` checks that the committed pages are fresh and
exits non-zero when they are stale.

## Atlas Wiki

Atlas is Codas's **live governance map**, not a post-hoc documentation generator.
Where a tool like CodeWiki or DeepWiki describes a finished codebase for human
readers, Atlas serves **agents and humans during development**: it guides an agent
before it edits (what to read, where new code belongs, what it may depend on) and
lets a human track plan progress and control deviation. It is prescriptive and
**verified** — every wiki claim is checked against repository facts
(`stale_wiki_claim`, and `generated_wiki_drift` for committed generated pages),
and the correctness core stays deterministic and LLM-free. Codas can also emit a verified **grounding
pack** that an external LLM-wiki generator consumes to produce an optional
human-prose doc-site, whose output Codas then verifies. The architecture decision
is recorded in `.trellis/tasks/06-19-wiki-architecture`.

## Status

Phases P0–P5 are complete. The living source of truth for per-phase and
per-deliverable status is `.codas/program.yml`; consult it rather than any
hardcoded summary here. Swift/Ciri-specific prototype code was removed;
ecosystem-specific extraction lives behind adapters.
