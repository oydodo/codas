# codas impact: CLI-first agent-query (P7), reverse-reachability over call-graph facts

## Status

PLANNING — the first P7 (Agent query interface) deliverable, recasting P7 as **CLI-first,
MCP-optional** (decision 2026-06-20).

## Decision: CLI + JSON is the query interface; MCP is optional sugar

Codas already emits deterministic JSON (`codas check --json`, `codas inventory --json`,
`codas preflight --task T --json`, receipts) — that JSON IS the agent-query contract. An
agent (Codex / Claude Code / Cursor) queries by shelling out + `jq`. MCP buys exactly ONE
thing — typed, self-describing tools in the agent loop — at the cost of a stateful daemon,
a non-deterministic surface (connection/version), auth, lifecycle, and headless/cron
fragility, all of which fight Codas's deterministic/stateless/auditable identity. Codas
already chose "file-convention + subprocess injection, NOT MCP" for the OSS LLM-wiki
backend (06-19-wiki-architecture); the same logic applies to agent-query.

**So P7's query interface is CLI-first:** the deterministic JSON + a thin set of query
subcommands so `jq` is optional. MCP, if ever built, is a **thin stateless role-integration
shell** that shells out to / read-only-calls the core (like `enforcement.py` shells out to
`codas check`; stdlib-only, never re-implements fact logic) — which itself proves the CLI
is the real interface and MCP is sugar.

## Scope (this task — the first query subcommand)

- **`codas impact <symbol|path> [--json]`** — "changing this affects whom": reverse
  reachability over the existing `calls` facts (the deterministic call-graph already in the
  inventory). Given a symbol (or a file's symbols), walk callers transitively to the set of
  affected caller scopes/files. Deterministic, stdlib-only, §11 (consumes facts via the
  inventory / ScanContext, no new extraction).
- Emit deterministic JSON (sorted, content-only) + a human view.
- Honor the same scope/roots discipline as inventory.

## Out of scope (later P7 slices / optional)

- `codas query symbols|imports|calls --select ...` (pre-shaped slices so jq is optional) —
  a sibling subcommand, separate slice.
- `codas schema` (emit the inventory/JSON schema so the agent need not reverse-engineer
  the shape).
- MCP thin shell (optional; only if a target runtime needs typed tools).
- Role Integrations (Codex/Claude/CI/human mappings) and the OSS LLM-wiki backend adapters
  — the other two P7 deliverables.
- Forward impact ("what does X depend on") if not needed first; reverse is the
  change-propagation direction (ties to the v3 propagation engine: impact = one hop of the
  worklist's reachable set).

## Acceptance criteria

- [ ] `codas impact <symbol>` returns the transitive caller set from `calls` facts,
      deterministic JSON, byte-identical across runs.
- [ ] Cycles in the call-graph terminate (visited-set), like the propagation worklist.
- [ ] 0 new extraction logic — pure projection/traversal over existing `calls` facts (§11,
      no adapter import in any new CLI/core path that isn't already allowed).
- [ ] `codas check .` = 0; inventory byte-identical (impact is a read-only query, adds no
      inventory facts); full suite green.

## Notes

- `impact` is the CLI face of the same reverse-reachability the **v3 propagation engine**
  needs (one hop = the worklist's "re-check dependents" step). Building it CLI-first now
  both delivers P7 value and prototypes the propagation traversal.
- Relates to: the `calls` call-graph facts (substrate), `codas preflight` (the existing
  task-scoped JSON query precedent).
