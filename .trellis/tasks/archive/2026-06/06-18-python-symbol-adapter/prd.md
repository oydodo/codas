# PRD: Python symbol adapter (symbol facts)

## Context

Groundwork for the last substantive P2 policy, `duplicate_implementation`
(`duplicate_symbol` in plan §10). That policy needs **symbol facts** — repeated
type/function names across modules — which no adapter emits yet. This slice adds
the facts only; the policy is a separate following slice. Mirrors the P1 pattern
(markdown / trellis adapters emit facts; policies consume them later).

Authority:
- `docs/codas-implementation-plan.html` §11 Adapter Boundary — Python adapter
  "Allowed To Know: modules, classes, functions, imports, pyproject" → "Must
  Emit: symbol facts, package facts." §10 — `duplicate_symbol` First
  Implementation: "Language adapters emit repeated type/function names." §17 — no
  LLM for P2 correctness.
- Adapter boundary rule (§11): ecosystem-specific reality stays in the adapter;
  core receives only normalized facts.

Determinism is non-negotiable (the inventory is asserted byte-identical across
runs). Parsing uses the stdlib `ast` module — deterministic, no third-party deps,
no LLM.

## Goals

1. `src/codas/adapters/python.py` with `extract_symbol_facts(repo, files)`
   returning frozen `SymbolFact` records for **top-level** (module-level) class
   and function definitions in tracked `.py` files: `{module, name, kind, line}`,
   `kind ∈ {class, function}` (async functions collapse to `function`).
2. Malformed / unparseable `.py` files are recorded in a `skipped` list, never
   raise (mirrors `extract_task_facts`).
3. Surface in `codas inventory . --json` as a `symbols` block:
   `{sources: [...], definitions: [...], skipped: [...]}`, all deterministically
   sorted.
4. `codas check .` unchanged (no policy consumes symbols yet → still 0 findings).
5. `codas inventory` stays byte-identical across two runs.

## Non-Goals (deferred)

- **The `duplicate_implementation` / `duplicate_symbol` policy** — next slice.
- **Nested / method / conditionally-defined symbols** (defs inside classes, `if
  TYPE_CHECKING`, functions, etc.). Only direct module-level `tree.body` defs are
  emitted; qualified-name handling is a later expansion.
- **Import facts and package facts** (pyproject) — §11 lists them but the
  duplicate policy needs only symbol facts; later.
- **Cross-language symbols** (Swift/TS adapters) — P3.
- **Decorator-aware overload/property collapsing**, re-export detection.

## Acceptance Criteria

- Every top-level class/function in a tracked `.py` file appears once in
  `inventory.symbols.definitions` with correct `module`, `name`, `kind`, `line`.
- A `.py` file with a syntax error appears in `symbols.skipped`, not in
  `definitions`, and does not fail the inventory.
- `symbols.definitions` sorted by `(module, line, name, kind)`; `sources` and
  `skipped` sorted; no timestamps → byte-identical inventory across two runs.
- `codas check .` → still 0 findings.
- `PYTHONPATH=src python3 -m unittest discover -s tests` passes (new tests added).
- Dogfooding: new adapter file under `codas-adapters`, new test under
  `codas-tests` — both already governed; `inventory.unowned` stays empty.
