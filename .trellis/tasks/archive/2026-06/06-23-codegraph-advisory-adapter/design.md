# CodeGraph advisory adapter design

## Scope

Affected concept: P7 agent-query call graph, extending `codas impact` with advisory
multi-language / cross-language edges while preserving the P3 adapter boundary and the
P5 deterministic inventory/call-fact contracts.

Program item: `program:P7:agent-query-interface`.

CodeGraph output is query-time context only. It is not a gate-grade fact stream.

## Boundary

Existing `CallFact` / `CallFacts` remain the deterministic, first-party Python call graph:

- included in `codas inventory`
- included in `FactSnapshot`
- included in `fact_delta`
- available to policies such as `fact_coupling` and `code_anchor`

CodeGraph uses a separate dataclass family, not `CallFact`:

- `CodeGraphCallFact`
- `CodeGraphCallFacts`

That separation is the main invariant. It prevents an advisory edge from being passed to
`merge_call_facts`, `FactSnapshot`, `diff_snapshots`, inventory projection, or any policy
that consumes `ctx.calls()`.

## Advisory fact shape

`src/codas/adapters/codegraph.py` owns the external CLI contract and normalized adapter
types:

```python
@dataclass(frozen=True)
class CodeGraphCallFact:
    caller_module: str
    caller_class: str
    caller_symbol: str
    caller_path: str
    caller_line: int
    callee_module: str
    callee_class: str
    callee_symbol: str
    callee_path: str
    callee_line: int
    resolution: str
    provenance: str  # always "codegraph"

@dataclass(frozen=True)
class CodeGraphCallFacts:
    edges: tuple[CodeGraphCallFact, ...]
    skipped: tuple[str, ...]
```

`resolution` is copied from CodeGraph when available. Missing values become
`"heuristic"` because CodeGraph is advisory; absence of a resolution tag must not look
gate-grade. `provenance` is explicit on every edge so JSON/text reports can identify mixed
graph sources without inference.

The adapter sorts normalized edges by caller path/class/symbol then callee
path/class/symbol/resolution/provenance. Malformed rows are ignored and recorded in
`skipped` as stable strings.

## CLI contract

`extract_codegraph_calls(repo, files, executable="codegraph")` shells out to an optional
external command. Missing binary, timeout, non-zero exit, invalid JSON, or unsupported
schema returns an empty `CodeGraphCallFacts` with a stable skipped reason. It never raises
during normal scan/query use.

Implementation should keep the parser tolerant because the exact CodeGraph JSON can vary:

- prefer a top-level list of edge objects or a top-level `edges` list
- accept common caller/callee object shapes
- accept flat caller/callee field names where present
- normalize paths relative to repo and only retain edges where both endpoints map to
  scanned files or repo-relative paths

Tests will use a fake executable, not a real Node dependency.

## ScanContext seam

`ScanContext` gets a lazy accessor:

```python
def codegraph_calls(self) -> CodeGraphCallFacts:
    ...
```

This accessor is policy-time/advisory-only:

- not called by `working_snapshot()`
- not called by `head_snapshot()`
- not called by `fact_delta()`
- not called by `build_inventory()`
- not exported through `codas query`
- not called by `run_check_with_context()`

Only query surfaces such as `codas impact` may call it.

## Impact merge

`compute_impact()` should become graph-source-aware without changing existing callers:

- deterministic calls are projected as source `"calls"` / provenance `"codas"`
- CodeGraph calls are projected as source `"codegraph"` / provenance `"codegraph"`
- reverse reachability runs over internal edge records, not only nodes
- output rows include deterministic attribution for the edge(s) that first reached the row
- text rendering labels advisory rows instead of blending them silently

Attribution is edge-owned. A node can be reached by multiple paths and mixed sources, so
`provenance` / `resolution` must not be guessed from the node. The BFS stores a sorted
`via` list per affected row:

```json
{
  "module": "pkg.caller",
  "class": "",
  "symbol": "run",
  "path": "pkg/caller.py",
  "distance": 1,
  "via": [
    {
      "callee_module": "pkg.target",
      "callee_class": "",
      "callee_symbol": "target",
      "callee_path": "pkg/target.py",
      "provenance": "codegraph",
      "resolution": "heuristic"
    }
  ],
  "provenance": ["codegraph"],
  "resolution": ["heuristic"]
}
```

If multiple same-distance edges reach the same caller, all are kept in sorted `via`.
`provenance` and `resolution` are sorted summaries derived from `via`, not independent
facts. Longer paths never overwrite the minimum-distance attribution. Existing callers
that only read `module` / `class` / `symbol` / `path` / `distance` continue to work.

`run_impact()` is the only place that merges `ctx.calls()` and `ctx.codegraph_calls()`.
Unit tests can call `compute_impact()` with deterministic calls only, preserving existing
behavior; new tests should exercise the merge helper or a fake `CodeGraphCallFacts`.

Open-world caveat stays. Advisory CodeGraph edges make the lower-bound larger, not
complete.

## Preflight reuse hints

`codas preflight` may display advisory reuse hints from CodeGraph, but only as a
presentation/query add-on:

- computed after the inventory/provenance block is built
- omitted completely when CodeGraph is absent or unusable
- tagged `provenance=codegraph`
- excluded from `inventory_hash`, task facts, active policy inputs and check findings

This keeps preflight deterministic for its existing governed payload while allowing an
installed CodeGraph to add optional orientation text.

## Invariants to test

1. CodeGraph absent: `run_inventory()` JSON is byte-identical before/after
   `ctx.codegraph_calls()` is invoked.
2. CodeGraph absent: `ctx.working_snapshot()` and `ctx.fact_delta()` are unchanged and
   contain only deterministic `CallFact` edges.
3. Policy isolation: `run_check()` never calls `ScanContext.codegraph_calls()`.
4. Fake CodeGraph output: `codas impact` JSON/text includes advisory affected rows tagged
   `provenance=codegraph` via edge-owned `via` attribution.
5. Preflight with CodeGraph absent is byte-identical to the current output; preflight with a
   fake CodeGraph adds only advisory reuse hints after provenance.
6. `pyproject.toml` dependency set stays unchanged.

## Documentation

Update the architecture decision / wiki claim only if implementation changes the product
contract beyond the task PRD. At minimum, source comments near the accessor and impact merge
must state advisory-only and off-hash/off-gate.
