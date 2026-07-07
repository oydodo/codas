# Implementation Plan - Multi-language reference dependency graph

## Preconditions

- Task remains planning until PRD/design/implement are reviewed.
- Use deterministic in-core tree-sitter adapters only.
- Use temporary language fixtures only.

## Steps

1. Define neutral reference dependency contract.
   - Add or document neutral `DefinitionRecord` and `ReferenceCandidate` shapes.
   - Add or document shared `resolve_reference_edges()` behavior.
   - Keep public seam as `ImportFacts`.

2. Choose and justify the first concrete language adapter.
   - Prefer an already-registered parser if available.
   - Record why this does not narrow the task to that language.

3. Verify first-language tree-sitter node shapes.
   - Use a small local probe or test helper for explicit reference syntax.
   - Record only implementation-relevant findings.

4. Add definition-index helpers in the first language adapter.
   - Reuse existing symbol extraction logic where possible.
   - Return deterministic mappings for names to definition records.

5. Add reference extraction helpers.
   - Walk parsed trees.
   - Collect candidate names and source line.
   - Keep grammar-specific logic in adapter module.

6. Extend language import/reference extraction.
   - Keep current import facts.
   - Add resolved reference-derived `ImportFact` entries with `target_path`.
   - Deduplicate by `(module, target, target_path)` keeping first line.
   - Sort with existing import ordering.
   - Update dependency/reporting wording touched by reference-derived edges so it does not falsely
     say every dependency came from an import statement.

7. Add tests.
   - Resolved references across files.
   - Property/field type, parameter type, return type, inheritance/protocol/implements/conformance,
     generic constraint if grammar support is verified.
   - Duplicate local names in different namespaces do not emit guessed simple-name edges.
   - Qualified-name exact match works when adapter provides qualified keys.
   - External/framework references do not emit first-party edges.
   - Existing import facts still behave.
   - `dependency_direction` violation from reference-derived edge.
   - Atlas dependency graph exact edge tuple.
   - HEAD/working snapshot symmetry for reference-derived edges.
   - Parser-unavailable deterministic degrade.

8. Add a short extension note.
   - Document what a second language adapter must implement.
   - Confirm no policy/schema change is needed.

9. Validate.
   - `PYTHONPATH=src python3 -m unittest discover -s tests`
   - `PYTHONPATH=src python3 -m codas check .`
   - `PYTHONPATH=src python3 -m codas wiki --verify .`
   - `PYTHONPATH=src python3 -m codas agents --verify .`

## Rollback Points

- If generic/constraint grammar is unstable, ship simpler explicit positions first and leave
  constraint extraction as follow-up.
- If ambiguity reporting creates confusing UX, keep ambiguity silent and only assert no guessed
  edge.
