# Design - Multi-language reference dependency graph

## Position

This task extends deterministic in-core tree-sitter adapters. It does not add a new fact family.
It projects high-confidence local references into existing `ImportFact` edges because current
consumers already understand first-party dependency edges through `target_path`.

Current shape:

- Python imports emit first-party `ImportFact` edges.
- Existing non-Python tree-sitter support can emit symbols/import declarations, but local
  same-target or same-package references may not produce `target_path`.
- `dependency_direction` consumes `ctx.imports().imports` and only acts when `target_path` is set.

New shape:

- Language adapters can emit both import-derived and reference-derived `ImportFact` edges.
- A reference becomes a dependency edge only when it resolves to exactly one first-party definition.
- Each edge remains a lower-bound fact. Missing edge means unknown, not no dependency.

## Neutral Contract

Each participating language adapter owns grammar extraction, but resolution uses neutral records.
Preferred shapes:

```python
@dataclass(frozen=True)
class DefinitionRecord:
    name: str
    qualified_name: str
    module: str
    path: str
    kind: str
    line: int

@dataclass(frozen=True)
class ReferenceCandidate:
    name: str
    qualified_name: str | None
    module: str
    path: str
    line: int
    syntax_kind: str
```

Adapters provide:

1. Definition index:
   - input: parsed modules;
   - output: `DefinitionRecord` values.
2. Reference extraction:
   - input: parsed modules;
   - output: `ReferenceCandidate` values from explicit syntax.
3. Conservative resolution:
   - shared helper `resolve_reference_edges(definitions, references) -> ImportFacts`;
   - exact qualified match with one definition -> emit `ImportFact`;
   - simple-name fallback with one definition -> emit `ImportFact`;
   - zero definitions -> unresolved;
   - multiple definitions -> ambiguous.

Keep public output as `ImportFacts`; do not expose language-specific types across the facts seam.

## First Concrete Implementation

Pick the first concrete language by implementation readiness and validation value. Swift is a
reasonable first choice because the existing optional `codas[swift]` tree-sitter parser and merge
path are already in place. That choice must stay an implementation detail: shared contract helpers
must be language-neutral, and grammar-specific logic must remain in the adapter so a later
TypeScript/Java/Kotlin/Rust adapter can implement the same contract without inheriting Swift
assumptions.

## Reference Extraction

Only extract from syntax that explicitly names a type or declaration target:

- property/field type annotations;
- parameter type annotations;
- return type annotations;
- inheritance/implements/protocol/conformance clauses;
- generic constraints and where clauses when node shapes are verified;
- other declaration signatures when a language adapter can prove the syntax is explicit.

Avoid expression inference, receiver inference, overload resolution, protocol dispatch, or
compiler-backed semantic assumptions in this task.

## Name Normalization

Reference syntax can contain wrappers and generic containers. The language adapter should preserve
qualified context when available and may also expose a simple fallback:

- optional/array/container wrappers -> inner named types;
- qualified names -> exact qualified key first; last-component fallback only if unique in the
  first-party index;
- namespaces/packages/modules/classes become part of `qualified_name` when the grammar exposes them;
- built-in/framework names naturally remain unresolved when absent from first-party index.

Do not hard-code large framework deny-lists unless tests prove unavoidable noise.

## `ImportFact.target` Semantics

This task keeps `ImportFact` as the dependency edge carrier. For Python imports, `target` remains an
imported dotted module name. For reference-derived edges, `target` is the referenced definition
label. Consumers that present the edge to humans must not assume every first-party dependency edge
comes from an import statement.

Required consumer wording changes:

- `dependency_direction` messages should say a unit "depends on" or a file "refers to" the target
  when the edge may be reference-derived.
- Atlas dependency graph can keep the same tuple shape, but docs/rendered wording should describe
  edges as dependencies, not only imports.

No new field is planned for the first slice. If implementation needs an origin flag, it must be
justified before code starts because it changes query/inventory schema.

## Snapshot And Hash Symmetry

Reference-derived edges are gate-grade, so they must be produced identically from working-tree
files and from git blob content at `HEAD`.

Required invariants:

- a clean committed non-Python fixture with reference-derived edges has empty `fact_delta()`;
- a dirty change that adds/removes a reference changes only the expected import/reference delta key;
- parser-unavailable runs are deterministic and never create guessed edges;
- inventory rendering is byte-identical across repeated runs on unchanged input;
- Python-only repos remain byte-identical to pre-task behavior.

## Ambiguity

Ambiguous local names must not create edges. The implementation needs deterministic observability.
Preferred minimal option:

- no new public fact type;
- ambiguous candidates do not emit edges;
- tests assert absence and deterministic behavior.

If implementers need user-visible diagnostics, add stable `skipped` entries only after checking
that existing skipped semantics remain clear.

## Guardrails

- No CodeGraph dependency.
- No new gating policy.
- No policy imports adapter code.
- No committed language fixtures under this repo's scanned roots.
- Existing import behavior remains intact.
- Output must be a deterministic lower bound: fewer edges is acceptable; guessed edges are not.

## Multi-Language Extension Rule

A second language adapter should need only:

- parser registration in the language registry;
- adapter-local definition indexing;
- adapter-local explicit reference extraction;
- reuse of the common conservative resolver or the same resolution contract;
- no policy, inventory, or `ImportFact` schema changes.

## Open Questions

- How much shared helper code belongs in `codas.facts.languages` vs language adapters.
- Whether ambiguous references should be exposed in `skipped`; default no.
