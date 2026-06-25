# CodeGraph advisory adapter implementation plan

## Preconditions

- Task remains in planning until this design and plan are reviewed.
- Do not apply `stash@{0}`.
- Ignore unrelated untracked `.claude/settings.local.json` and
  `codas-system-diagram.html`.
- Keep `pyproject.toml` core dependencies unchanged.

## Steps

1. Add `src/codas/adapters/codegraph.py`.
   - Define `CodeGraphCallFact` / `CodeGraphCallFacts`.
   - Add tolerant JSON parser for fake and real CodeGraph-like edge shapes.
   - Shell out through `subprocess.run`, graceful-empty on missing/unusable binary.
   - Deterministically sort edges and skipped reasons.

2. Add `ScanContext.codegraph_calls()`.
   - Import only through the facts seam.
   - Cache under a distinct `codegraph_calls` key.
   - Do not thread into snapshots, deltas, inventory, or query schema.

3. Extend impact projection.
   - Merge `ctx.calls()` with `ctx.codegraph_calls()` in `run_impact()`.
   - Preserve existing deterministic-only `compute_impact()` behavior.
   - Add edge-owned `via` attribution plus derived provenance/resolution summaries to JSON
     affected rows.
   - Render advisory rows visibly in text.

4. Add advisory preflight reuse hints.
   - Compute hints only after the normal inventory/provenance payload is built.
   - Omit the block when CodeGraph is absent or empty.
   - Tag every hint with `provenance=codegraph`.
   - Do not feed hints into inventory, provenance hashes, task facts, or policies.

5. Add focused tests.
   - Adapter absent-binary test.
   - Adapter fake-output parser test.
   - Impact advisory-edge report test, including mixed-source attribution for one reached
     node.
   - Preflight absent-binary byte-identical test.
   - Preflight fake-output advisory-hints test.
   - Inventory/hash isolation test.
   - Snapshot/fact_delta isolation test.
   - Check/policy isolation test using a patched accessor that fails if called.

6. Run validation.
   - `PYTHONPATH=src python3 -m unittest discover -s tests`
   - `PYTHONPATH=src python3 -m codas check .`
   - `PYTHONPATH=src python3 -m codas wiki --verify .`
   - `PYTHONPATH=src python3 -m codas agents --verify .`

7. Finish.
   - Re-run `git status --short`.
   - Update specs only if implementation reveals a reusable rule not already captured.
   - Commit with task-scoped changes only.

## Rollback points

- If CodeGraph CLI shape is incompatible, keep adapter parser fake-output compatible and
  return empty for unknown real schemas; query surface remains usable.
- If impact output compatibility breaks existing tests, make provenance fields additive and
  keep deterministic-only rows sorted exactly as before.
