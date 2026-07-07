# Multi-language call graph coverage

## Goal

Make `codas impact` useful across non-Python and multi-language repos by improving advisory
CodeGraph call-graph coverage while preserving Codas gate/hash invariants.

Existing CodeGraph support is already implemented as advisory and wired into `codas impact`, but
real multi-language validation must determine whether the adapter understands current CodeGraph
output and whether impact results are useful enough. Any single repo, including Swift/Ciri, is only
a validation sample, not the task boundary.

## Requirements

- Treat CodeGraph facts as advisory-only:
  - may feed `codas impact` and preflight hints;
  - must not enter inventory, snapshots, deltas, hashes, or gating policies;
  - must carry provenance/resolution.
- Validate CodeGraph on at least one real multi-language repo and one reduced fixture:
  - record the named languages in scope;
  - record indexed file counts per language;
  - confirm indexed languages and file coverage;
  - confirm real DB/status schema and call-edge shape;
  - confirm path normalization to Codas scanned file paths;
  - measure examples where impact becomes non-empty.
- Improve Codas's CodeGraph adapter only where needed for real CodeGraph output:
  - schema compatibility;
  - path normalization;
  - language-agnostic node kind mapping into normalized call facts;
  - deterministic sorting and graceful degrade.
- Preserve existing deterministic `compute_impact()` behavior for in-core `CallFacts`.
- Capture unsupported call forms as open-world gaps, not false denials.
- Produce a follow-up decision inside the task:
  - CodeGraph advisory coverage is enough for P2 now; or
  - add in-core conservative per-language call extractors for gate-grade lower-bound calls.

## Acceptance Criteria

- [ ] On a real multi-language repo, `codas impact <symbol>` returns at least one non-empty
      advisory caller path involving a non-Python file with `provenance=codegraph`; the completed
      task records which language(s) were validated.
- [ ] When CodeGraph is absent, `impact`, preflight, inventory, check, and hash behavior stay
      unchanged.
- [ ] Real CodeGraph SQLite/status output used by current CLI version is parsed for the validated
      repo. Unsupported schema is a research result only and does not satisfy the coverage goal.
- [ ] Tests cover real-schema parsing, path normalization, advisory text/JSON output, and
      no-gate/no-hash isolation.
- [ ] Isolation tests prove CodeGraph facts do not affect inventory JSON/hash, working/head
      snapshots, `fact_delta()`, `codas query calls`, query schema, `run_check()`, or policy inputs.
- [ ] `.trellis/tasks/06-27-multilang-call-graph-coverage/research/codegraph-validation.md` records
      CodeGraph version, status JSON shape, SQLite table DDL, indexed files by language, parsed
      call-edge count, skipped reasons, exact `codas impact <symbol>` examples, unresolved
      language/call forms, and whether separate tree-sitter conservative call extractor tasks are
      needed.
- [ ] Validation: unit tests, `codas check .`, `codas wiki --verify .`, and `codas agents --verify .`.

## Notes

- This task is advisory P2 by default.
- Do not let CodeGraph facts feed `fact_coupling` or `dependency_direction`.
- If gate-grade calls become required for a language, split or extend with in-core tree-sitter
  conservative extractor work after CodeGraph coverage is measured.
