# Multi-language reference dependency graph

## Goal

Make Codas understand first-party file and unit dependencies that are expressed by local code
references, not by import declarations, across supported languages.

Many ecosystems have same-target or same-package visibility where first-party dependencies do not
show up as imports. Codas currently models dependency direction through `ImportFact.target_path`.
This task generalizes that fact stream: language adapters may emit dependency edges from
high-confidence type/symbol references when they resolve to a unique first-party definition.

Swift/Ciri is one motivating validation case, not the task boundary. The task must be shaped around
a reusable tree-sitter adapter contract and at least one concrete language implementation.

## Requirements

- Define a language-neutral adapter contract for reference-derived dependency edges:
  - adapters produce neutral `DefinitionRecord` and `ReferenceCandidate` values;
  - shared resolution code maps candidates to existing `ImportFact` edges;
  - emit existing `ImportFact(module=<referencing file>, target=<referenced name>, target_path=<definition file>, line=<reference line>)`.
- Treat `ImportFact.target` as a generic dependency label when `target_path` is set, not only as an
  import module name.
  - Update user-facing wording in dependency/reporting surfaces touched by reference-derived edges
    from "imports" to "depends on" or "refers to" where needed.
  - Do not add a schema field unless implementation proves consumers need to distinguish
    import-derived vs reference-derived edges.
- Build at least one concrete implementation on the existing tree-sitter-backed language adapter
  surface, selected by implementation readiness and testability.
  - Swift is acceptable as an initial implementation because the parser already exists, but the
    contract must not encode Swift-only grammar concepts.
  - The design must leave an obvious path for TypeScript/Java/Kotlin/Rust/etc. adapters.
- Resolution rules:
  - exact qualified key match with one first-party definition -> emit edge;
  - simple-name fallback with one first-party definition -> emit edge;
  - zero definitions -> unresolved, no edge;
  - multiple definitions -> ambiguous, no guessed edge.
- Reference positions should be explicit and high signal:
  - type annotations;
  - parameter and return types;
  - inheritance/implements/protocol/conformance clauses;
  - generic constraints where grammar support is clear;
  - other language-specific declaration signatures only when deterministic.
- Preserve Codas gate invariants:
  - deterministic output, sorted facts, no LLM;
  - graceful degrade when optional parser support is unavailable;
  - no committed non-Python fixtures under scanned roots;
  - no policy imports from adapters.

## Acceptance Criteria

- [ ] A multi-file fixture in at least one non-Python language emits first-party reference edges
      with `target_path` using existing `ImportFact`, and the implementation documents which
      language adapter fulfilled the first slice.
- [ ] The contract for adding a second tree-sitter language adapter is documented in the design or
      code comments without requiring changes to policies or `ImportFact`.
- [ ] Ambiguous duplicate local definitions do not create guessed edges.
- [ ] Existing Python-only inventory, snapshots, and `fact_delta` stay byte-identical.
- [ ] A clean committed non-Python fixture with reference-derived edges has empty `fact_delta()`;
      after changing one reference, the delta contains only the expected import/reference key
      added/removed.
- [ ] Parser-unavailable behavior is deterministic: reference-derived edges are absent, skipped
      sources are stable, and no false dependency is emitted.
- [ ] `dependency_direction` can report a violation caused only by a reference-derived edge, and
      the message uses dependency/reference wording rather than claiming an import statement exists.
- [ ] Atlas dependency graph includes the exact reference-derived edge tuple
      `{module: <referencing file>, target: <referenced name>, target_path: <definition file>}`.
- [ ] External/framework references remain unresolved (`target_path=None` or no edge) and do not
      create false first-party dependencies.
- [ ] Tests cover this fixture matrix for the first implementation: property/field type,
      parameter type, return type, inheritance/protocol/implements/conformance, generic constraint
      if supported by verified grammar, external/framework ignored, duplicate simple names in
      different namespaces produce no guessed simple-name edge.
- [ ] Validation: unit tests, `codas check .`, `codas wiki --verify .`, and `codas agents --verify .`.

## Notes

- This is gate-grade and may enter `ctx.imports()`, inventory, snapshots, deltas, and policies.
- Do not solve call graph here.
- Do not use CodeGraph here; CodeGraph stays advisory-only.
