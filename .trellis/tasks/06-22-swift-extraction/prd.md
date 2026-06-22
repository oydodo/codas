# Swift language extraction — tree-sitter symbols+imports thin slice + LanguageAdapter abstraction (gate-semantics)

## Goal

Give Codas a SECOND extraction language (Swift) so it can govern Swift repos, starting with a
thin slice: top-level **symbols + imports** via tree-sitter. Establish the multi-language seam
without disturbing the proven, byte-identical Python path. This unlocks running Codas on
`/Users/oydodo/Documents/repo/swift/ciri` (adoption is a later task).

## Background

- Codas extraction is Python-only (stdlib `ast`); deps are `pyyaml` only. Fact schema
  (`SymbolFact`/`ImportFact`) + downstream policies are already language-neutral; only the
  PARSE + node-inspection layers are Python-coupled.
- `tree-sitter-swift` (PyPI, prebuilt wheels, no Swift toolchain) is the substrate.
- Open-world invariant: static facts are a LOWER BOUND — a CST without type resolution yields
  fewer facts (no call-graph), never a false denial. Swift fits this cleanly.

See `design.md` for the technical shape (additive-merge seam, optional-extra dependency,
graceful degrade, deferred call-graph/dep-direction).

## Requirements

### R1 — Optional dependency, graceful degrade
- Swift support is an optional extra (`pip install codas[swift]` → tree-sitter + tree-sitter-swift).
  Core install stays `pyyaml`-only.
- tree-sitter imported lazily; absent extra OR no `.swift` files → no-op returning empty facts,
  `.swift` paths routed to `skipped` (never raises).

### R2 — Swift symbol + import extraction
- `adapters/swift_parse.py` (lazy tree-sitter parse) + `adapters/swift.py`
  (`extract_swift_symbols`, `extract_swift_imports`) reusing the neutral `SymbolFact`/`ImportFact`.
- Symbols: top-level `class`/`struct`/`enum`/`protocol`/`extension`/`func`/`actor`/`typealias`
  (top-level only — open-world lower bound). Imports: `import X` → target=module, target_path=None.

### R3 — Additive-merge seam, byte-identical preserved
- `ScanContext.symbols()`/`imports()` merge Python facts + language facts, re-sorted by the
  existing key. A repo with no `.swift` files → empty extra → byte-identical output.
- `calls()` unchanged (Swift call-graph deferred).

### R4 — Light language registry
- `facts/languages.py` registry (`LanguageExtractor` per non-Python language) so the merge call
  is language-blind; Python stays its own stdlib path. (codex to confirm registry-now vs YAGNI.)

### R5 — Tests on a Swift fixture
- Committed `.swift` fixture; tests for each symbol kind, imports, malformed→skipped,
  graceful-degrade (tree-sitter absent), byte-identical Python-only, deterministic merge sort.

## Acceptance Criteria

- [ ] With tree-sitter-swift installed, `codas inventory` on a Swift fixture emits Swift symbol
      + import facts (top-level kinds, sorted, deterministic across two runs).
- [ ] Without the extra (tree-sitter import fails), `.swift` files appear in `skipped`, no crash,
      empty Swift facts.
- [ ] Codas's OWN inventory is byte-identical before/after the seam change (no `.swift` here);
      `codas check .` = 0; full suite green; `agents`/`wiki --verify` clean.
- [ ] `dependency_direction` does not fire on Swift imports (target_path=None) — no false positives.
- [ ] New files map to owned units (`missing_structure_owner` clean); no `duplicate_implementation`
      from the new extractor symbols.
- [ ] A 3rd language would need only a new `LanguageExtractor` entry + adapter module (seam stated).

## Constraints

- **Gate-semantics** (touches fact extraction → byte-identical hash) → codex DESIGN review
  BEFORE impl (done as part of this task), and byte-identical must be proven, not assumed.
- Python core stays zero-new-deps; tree-sitter is optional-extra only.
- §11: `facts` may import `adapters` (existing direction); no new dependency_direction violation.
- Determinism: sort all outputs; tree-sitter parse is deterministic.

## Notes

- Sources: https://pypi.org/project/tree-sitter-swift/ , https://pypi.org/project/tree-sitter/
- DEFERRED (separate tasks): Swift call-graph, Swift dependency_direction + SPM module map,
  member-level symbols, `ciri` adoption/governance.
