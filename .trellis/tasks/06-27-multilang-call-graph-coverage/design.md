# Design - Multi-language call graph coverage

## Position

This task improves multi-language impact, not gate enforcement.

CodeGraph is the first path because the adapter already exists and is wired into `run_impact()`.
The architecture decision remains: CodeGraph is external, index-backed, and advisory. It may widen
impact/reuse hints, but cannot feed hash-bound inventory or gate policies.

The task must separate two outcomes:

1. Advisory multi-language impact through CodeGraph.
2. Possible later gate-grade calls through in-core tree-sitter conservative per-language extractors.

## Current State

- `ScanContext.codegraph_calls()` returns `CodeGraphCallFacts`.
- `run_impact()` merges deterministic Python `ctx.calls()` with advisory `ctx.codegraph_calls()`.
- `compute_impact()` remains deterministic-only.
- Tests enforce inventory/snapshot/check isolation.

## Workstream A - Real CodeGraph Validation

Run CodeGraph against a real multi-language repo and a reduced fixture. Record:

- CodeGraph version/package/commit when available;
- command needed to initialize/update index;
- `codegraph status --json` shape;
- SQLite schema for nodes and edges;
- indexed file counts by language;
- parsed call-edge counts and skipped reasons;
- edge kind values for calls;
- path format: absolute, repo-relative, or project-relative;
- symbol names and qualified names for functions, methods, initializers/constructors, and static calls;
- which languages are indexed with useful call edges.
- whether the sample is broad enough for this task or only evidence for a follow-up language.

This is evidence gathering first. Do not change Codas behavior until real output is understood.

## Workstream B - Adapter Compatibility

If real CodeGraph output differs from the current parser, update `src/codas/adapters/codegraph.py`
within advisory constraints:

- tolerate schema variations where deterministic;
- normalize paths relative to repo;
- skip outside-repo or unknown-file edges;
- always set normalized fact `provenance="codegraph"`;
- map CodeGraph edge provenance/kind/confidence into `resolution` or another additive
  non-source field;
- keep sorted edge output;
- degrade to empty with a skipped reason when unsupported.

## Workstream C - Impact Presentation

Make advisory rows visible enough for users:

- text output should mark `provenance=codegraph`;
- JSON output should keep `via` edges with provenance/resolution;
- open-world note remains present;
- no claim that absence proves no impact.

## Completion Gate

This task is not complete if real CodeGraph output is only "unsupported". Unsupported real schema
should produce a research note and a follow-up task, while the coverage task remains incomplete or
is explicitly rescoped by the user. Completion requires at least one real multi-language validation
where `codas impact` surfaces a non-empty advisory edge involving a non-Python file.

## Workstream D - Decision on In-Core Calls

After measuring CodeGraph:

- If CodeGraph covers enough cases, close with advisory P2 done.
- If not, write follow-up scopes for in-core conservative call extractors by language:
  - same-file free function;
  - unique global function;
  - unique type initializer/constructor;
  - `TypeName.staticMethod(...)` or equivalent;
  - unresolved for overloads, protocol/interface dispatch, inferred receiver, dynamic dispatch,
    generics, macros, or reflection.

Do not mix gate-grade extractors into this task unless user explicitly expands scope.

## Guardrails

- CodeGraph facts stay off inventory, snapshots, deltas, and gates.
- No Node dependency added to Python package dependencies.
- Missing CodeGraph is normal: empty advisory facts, not failure.
- No large copied fixtures from external repos.
