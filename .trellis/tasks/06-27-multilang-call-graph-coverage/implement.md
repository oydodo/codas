# Implementation Plan - Multi-language call graph coverage

## Preconditions

- Task remains planning until PRD/design/implement are reviewed.
- Network/package installs are not assumed. If CodeGraph is not installed, request approval before
  installing or use existing local binary if present.
- Keep CodeGraph advisory-only.

## Steps

1. Inspect local CodeGraph availability.
   - `command -v codegraph`
   - `codegraph --help`
   - If absent, decide whether to install or use a checked-in/fake fixture for parser tests.

2. Validate against a real multi-language repo and reduced fixture.
   - Run CodeGraph status/init/update commands as needed.
   - Inspect SQLite schema and sample nodes/edges across available languages.
   - Save findings in `.trellis/tasks/06-27-multilang-call-graph-coverage/research/codegraph-validation.md`.
   - Include CodeGraph version, status JSON, SQLite DDL, indexed files by language, parsed edge
     counts, skipped reasons, and exact impact examples.

3. Compare real output to current adapter.
   - Path normalization.
   - Edge kind naming.
   - Node kind/name/qualified_name shape.
   - Provenance values.

4. Patch `src/codas/adapters/codegraph.py` only if needed.
   - Keep graceful-empty behavior.
   - Keep deterministic sorting.
   - Keep normalized fact `provenance="codegraph"`; map source confidence/kind to `resolution`.
   - Add focused parser/schema tests.

5. Patch impact presentation only if current output hides advisory edges.
   - Preserve deterministic-only `compute_impact()` behavior.
   - Keep additive JSON fields only.

6. Add tests.
   - Real-schema fixture for multi-language DB rows.
   - Path normalization from absolute CodeGraph paths to repo-relative Codas paths.
   - `run_impact()` includes advisory non-Python edge.
   - Missing CodeGraph unchanged.
   - `run_check()` never calls `codegraph_calls()`.
   - Inventory JSON/hash byte-identical before/after `codegraph_calls()`.
   - Working/head snapshots unchanged after `codegraph_calls()`.
   - `fact_delta()` unchanged after `codegraph_calls()`.
   - `codas query calls` and query schema exclude CodeGraph facts.

7. Write task decision note.
   - Path: `.trellis/tasks/06-27-multilang-call-graph-coverage/research/codegraph-validation.md`.
   - Summary of CodeGraph language coverage.
   - Missing call forms.
   - Recommendation: close P2 with advisory CodeGraph or open in-core conservative call tasks.

8. Validate.
   - `PYTHONPATH=src python3 -m unittest tests.test_codegraph tests.test_impact`
   - `PYTHONPATH=src python3 -m unittest discover -s tests`
   - `PYTHONPATH=src python3 -m codas check .`
   - `PYTHONPATH=src python3 -m codas wiki --verify .`
   - `PYTHONPATH=src python3 -m codas agents --verify .`

## Rollback Points

- If real CodeGraph schema is unstable, keep current adapter behavior and close with a research
  note plus unsupported-schema skipped reason only after explicit rescope; unsupported schema does
  not satisfy the P2 coverage acceptance criteria.
- If a language needs gate-grade impact, do not promote CodeGraph. Create a separate in-core
  conservative call extractor task.
