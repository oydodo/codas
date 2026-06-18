# PRD — P4 C3: preflight context pack

## Context

P4 (`program:P4:preflight-receipts`) deliverable "Task context pack"; exit "Agent
work can prove which task/inventory/check it used." C1 shipped provenance hashes,
C2 the receipt. This slice ships the **Context Pack** — the read-first context an
agent assembles *before* work — closing P4.

**Context Pack** (authoritative, CONTEXT.md): "Task-specific context Codas prepares
for an agent before work begins, including relevant concepts, read-first files,
risks and required updates." The CLI already stubs `codas preflight --task`.

## Goal

`codas preflight [--task NAME] [--json]` emits a deterministic context pack: the
task being worked, the read-first authoritative sources + dogfooding protocol, the
active policies that will govern the work, and the C1 provenance pinning the repo
state — so an agent (and its receipt) can prove what it preflighted against.

## Requirements

1. `app/preflight.py::build_context_pack(repo, task_id=None) -> dict`:
   - `read_first`: sorted `config.authoritative_sources`; `supporting`: sorted
     `config.supporting_sources`; `dogfooding_protocol`.
   - `policies`: sorted `[{id, severity}]` from `policies.yml`.
   - `provenance`: `compute_provenance(repo)` (inventory_hash + policy_version).
   - `task`: when `task_id` is given, the matching Trellis `TaskFact`
     (`id/status/package/dev_type/priority/archived`) or `null` if unmatched; when
     omitted, `null` plus an `available_tasks` list of ids.
   - shape `{schema_version, kind: "context_pack", task, available_tasks, read_first,
     supporting, dogfooding_protocol, policies, provenance}`. Deterministic, sorted,
     no timestamp (timestamp lives on the receipt, C2).
2. `cli.py`: implement the `preflight` command (currently stubbed "planned but not
   implemented") — print the pack as JSON (`--json`) or a human summary. Leave
   `wiki`/`doctor` stubbed.

## Acceptance criteria

- `codas preflight . --json` emits the pack; `read_first` matches the config
  authoritative sources; `policies` lists every declared policy with its severity;
  `provenance` equals `compute_provenance(repo)`.
- `--task <id>` populates `task` with that Trellis task's facts; an unknown id →
  `task: null`; no `--task` → `available_tasks` listing the repo's task ids.
- `build_context_pack` is deterministic across two runs (no timestamp).
- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings"; `codas inventory`
  byte-identical; full suite green.

## Non-goals

- "Risks and required updates" (Structure Map `must_update_if_changed`, document
  `updates_when`) in the pack — a later enrichment facet; C3 ships task + read-first
  + policies + provenance.
- Reading/inlining file *contents* — the pack lists paths to read, not their bodies.
- Auto-writing the pack to disk or into a receipt — `preflight` prints; wiring a
  task field onto the receipt is a later facet.
- Implementing `wiki`/`doctor` — out of scope (P5 / later).
