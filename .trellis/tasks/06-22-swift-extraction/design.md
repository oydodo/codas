# Design — Swift language extraction (thin slice)

Companion to `prd.md`. **Gate-semantics** (touches fact extraction → the byte-identical
inventory) → codex DESIGN review REQUIRED before impl. Worktree `harness-swift-extraction` /
`feat/swift-extraction`.

## 0. Locked decisions (from brainstorm)

- Parser substrate = **tree-sitter** (`tree-sitter-swift` on PyPI, prebuilt wheels all
  platforms incl. macOS ARM64, no Swift toolchain, in-process).
- **Thin slice**: Swift **symbols + imports** only. Call-graph DEFERRED (CST has no type
  resolution → no sound first-party call edges).
- Adoption target (later, separate): `/Users/oydodo/Documents/repo/swift/ciri`.

## 1. Current extraction seam (verified @ feat/swift-extraction base)

- `facts/context.py:ScanContext._parsed()` (138) — one `parse_python_modules(repo, files)` per
  run, cached. `symbols()` (149) / `imports()` (155) / `calls()` (170) project from it.
- `adapters/python.py`: `SymbolFact(module, name, kind, line)` + `SymbolFacts(definitions,
  skipped)`; `ImportFact(module, target, target_path, line)` + `ImportFacts(imports, skipped)`.
  Symbol sort key `(module, line, name, kind)`. **A file whose parse fails goes to `skipped`,
  never raises** (`python.py:63`) — the graceful-degrade precedent Swift reuses.
- Dependencies (`pyproject.toml`): only `pyyaml>=6.0`; Python parsing is stdlib `ast`, zero
  parser deps. **tree-sitter is the FIRST native code dep** → must not burden the Python core.

## 2. Dependency strategy — optional extra + graceful degrade [KEY gate concern]

- Add an **optional extra**: `pip install codas[swift]` → `tree-sitter>=0.23, tree-sitter-swift`.
  The core install stays `pyyaml`-only; a Python-only user pulls nothing new.
- `adapters/swift_parse.py` imports tree-sitter **lazily inside the parse function**, guarded:
  if the import fails (extra not installed) OR there are no `.swift` files, Swift extraction is a
  **no-op** that returns empty facts and routes any `.swift` paths to `skipped`. So:
  - Python-only repo, extra absent → zero behavior change, byte-identical (§7).
  - Swift repo, extra absent → `.swift` files appear in `skipped` (visible, honest), never crash.
  - Swift repo, extra present → real Swift symbol/import facts.
- This is consistent with the **open-world invariant** ([[codas-perception-model]]): static
  facts are a LOWER BOUND; missing a parser yields fewer facts, never a false denial.

## 3. The additive-merge seam (byte-identical preserved BY CONSTRUCTION)

The core move: `symbols()` / `imports()` **merge** the Python facts with extra-language facts.
For a repo with no `.swift` files (every Codas repo today), the extra path returns EMPTY, so the
merged + re-sorted output is byte-for-byte the Python-only output. No Python code path changes.

```
# facts/context.py
def symbols(self):
    if "symbols" not in cache:
        py = extract_symbol_facts_from_parsed(self._parsed())
        extra = extract_language_symbols(self.repo, self.files)   # swift today; empty if none
        cache["symbols"] = _merge_symbol_facts(py, extra)         # combine + sort by SAME key
    return cache["symbols"]
```

`_merge_symbol_facts` **EARLY-RETURNS the unchanged Python `SymbolFacts` object when the extra
facts are empty** (review B3) — byte-identical BY INSPECTION, not by an argument about sort
stability. Only when extra is non-empty does it concatenate `definitions` + re-sort by
`(module, line, name, kind)` and concatenate+sort `skipped`. Same for `imports()` (key
`(module, line, target)`, `python.py:126`). Identity test: `merge(py, EMPTY)` returns `py`
unchanged. `calls()` is UNCHANGED (Swift contributes no call edges — thin slice).

## 4. Swift extraction (tree-sitter)

- `adapters/swift_parse.py` — `parse_swift_modules(repo, files) → ParsedSwiftModules` (lazy
  tree-sitter; `.swift` files only; unreadable/unparseable → `skipped`, mirrors python_parse).
- `adapters/swift.py` — `extract_swift_symbols(parsed) → SymbolFacts`,
  `extract_swift_imports(parsed) → ImportFacts` (reuse the SAME `SymbolFact`/`ImportFact`
  dataclasses — language-neutral schema, codex-confirmed agnostic).
  - **Symbols**: top-level declarations via tree-sitter node kinds — `class_declaration`,
    `struct_declaration`, `enum_declaration`, `protocol_declaration`, `extension_declaration`,
    `function_declaration` (+ top-level `typealias`/`actor`). `kind` ∈ existing strings +
    new `struct`/`enum`/`protocol`/`extension`/`actor`/`typealias` (just strings — the
    policies treat `kind` opaquely). **Top-level only** (mirrors Python's module-level scope),
    an explicit open-world lower bound documented in a banner.
  - **Imports**: `import_declaration` → `ImportFact(module=<.swift path>, target=<module name
    e.g. "Foundation">, target_path=None, line)`. `target_path=None` always for the thin slice
    (Swift module→file resolution = SPM/Xcode target map, DEFERRED) → see §5.

## 5. Deferred (placed, not built)

- **Swift call-graph** — CST gives no type/overload/protocol-dispatch resolution; sound first-
  party edges need a resolver. `calls()` stays Python-only.
- **Swift dependency_direction** — needs Swift import target→unit resolution (SPM `Package.swift`
  / Xcode targets, not file paths). Because Swift `ImportFact.target_path` is `None`,
  `dependency_direction` (which keys on first-party `target_path`) simply never fires on Swift
  imports → **no false positives** (verified against the policy's logic). Swift dep-direction is
  a later task once a Swift module map exists.
- **Swift member-level symbols** (methods, nested types) — top-level first.
- **Swift fact-delta / fact_coupling** (review N1) — `head_snapshot` reads `.py` blobs ONLY
  (`snapshot.py:43`→`git.list_python_paths_at_head`, `.py` filter at `git.py:87`), while the
  merge lands in `working_snapshot` via `symbols()`/`imports()`. So on a Swift repo every Swift
  symbol/import would read as permanently "added" in `fact_delta` → `fact_coupling` could
  mis-fire. HARMLESS on Codas (zero `.swift`) and NEVER serialized (delta/snapshots are
  out-of-inventory, `context.py:176-185`). Swift is OUT OF SCOPE for `fact_delta`/`fact_coupling`
  until a Swift HEAD-blob reader exists; an impl must NOT naively assume symmetry.
- **`ciri` adoption** — running real governance on the user's repo is post-capability.
- **CodeGraph multi-language fact adapter** — the bigger direction this slice feeds: an
  external multi-language fact source (CodeGraph) for the ADVISORY tier (impact / reuse /
  multi-lang claim resolution), while THIS hand-built tree-sitter Swift adapter stays the
  gate-grade DETERMINISTIC tier. See `docs/codas-fact-claim-maintenance-milestone.md`.

## 6. LanguageAdapter abstraction (light)

Not the full Protocol the first sketch implied. A thin registry in `facts/languages.py`:

```python
@dataclass(frozen=True)
class LanguageExtractor:
    name: str
    extensions: tuple[str, ...]
    symbols: Callable[[Path, tuple[str, ...]], SymbolFacts]
    imports: Callable[[Path, tuple[str, ...]], ImportFacts]

LANGUAGES = (SWIFT,)   # each non-Python language; Python stays the stdlib-ast core path

def extract_language_symbols(repo, files) -> SymbolFacts: # union over LANGUAGES, each filters its exts
def extract_language_imports(repo, files) -> ImportFacts:
```

Python is NOT folded into the registry (keep the proven stdlib path + its single-parse cache
seam untouched — minimize blast radius). A 3rd language = one `LanguageExtractor` entry + its
adapter module. ← codex: is a registry worth it now, or just call Swift directly until a 3rd
language exists (YAGNI)? The registry is ~15 lines and makes the merge call language-blind.

## 7. Gate-semantics & invariants

- **Byte-identical**: PROVE the Codas inventory is unchanged (no `.swift` → empty extra → §3
  early-return → identical). Test: inventory hash before/after the seam change is equal; a
  snapshot test over `symbols()`/`imports()` on a Python-only fixture is unchanged. **CRITICAL
  (review B1): never commit a `.swift` fixture under a scanned root.** Codas's `.codas/config.yml`
  has `roots: ["."]` → the whole repo (incl. `tests/`) is scanned, and the scanner is
  extension-agnostic (`index.py`: no `.py` allowlist; the `.py` filter is adapter-only) → a
  committed `.swift` would enter Codas's OWN inventory and move the hash. Today `tests/` has ZERO
  committed non-`.py` files (every fixture is `tmp_path`). The Swift fixture MUST be written to
  `tmp_path` at test time, like every other Codas fixture — see §8.
- **Swift-repo determinism requires the extra installed UNIFORMLY (review B2)**: on a repo WITH
  scanned `.swift`, the inventory bytes depend on whether `codas[swift]` is installed — present →
  real Swift facts, absent → those `.swift` paths in `inventory[...].skipped` (`inventory.py:235,
  250`). Both are individually deterministic, but MIXED environments (CI with the extra, a dev
  without) produce DIVERGENT inventories on a Swift repo. Operational rule: any environment that
  runs `codas check` on a Swift repo must install `codas[swift]`. (Codas itself is immune — zero
  scanned `.swift`.)
- **Swift dup-detection scope (review N3)**: `duplicate_implementation`/`duplicate_symbol` gate on
  `module.startswith("src/")` (`SCOPE_PREFIX="src/"`). Swift dup-detection fires ONLY for `.swift`
  under `src/`; a `Sources/`-layout Swift repo gets none (a later scope-config concern, not this
  task).
- **structure ownership**: new files `adapters/swift.py`, `adapters/swift_parse.py`,
  `facts/languages.py` land under owned units (`codas-adapters`, `codas-facts`) →
  `missing_structure_owner` clean. tests under `tests`.
- **`duplicate_implementation`/symbol naming**: Swift extractor functions get unique top-level
  names (`extract_swift_symbols`, not `extract_symbol_facts*`) to avoid the cross-module
  name-collision gate.
- **§11 dependency direction**: `facts/languages.py` (codas-facts) imports `adapters/swift`
  (codas-adapters) — the SAME direction `facts` already imports `adapters/python` (allowed).
  No new violation.
- **`kind` is opaque to policies EXCEPT `policy_registry.py:64` (review N2)**: it switches on
  `kind == "function"`, but path-gated to `src/codas/policies/` (`_POLICY_PREFIX`) + `check_`
  prefix → a Swift `func` can never reach it. Safe; do NOT govern Swift under that prefix.
- **tree-sitter pin (review N4, resolved)**: `tree-sitter-swift==0.7.3` depends on
  `tree-sitter~=0.23` (verified PyPI metadata), requires-python ≥3.8 (Codas ≥3.9 OK), abi3 wheels
  cp38+ incl. macOS arm64. Pin the extra as `tree-sitter~=0.23, tree-sitter-swift~=0.7`; verify
  the `Language()/Parser()` API against the installed `tree-sitter` at impl (0.23 surface).
- **Determinism**: tree-sitter parse is deterministic; sort all outputs; no dict-order leakage.

## 8. Test plan

- Swift fixture is WRITTEN TO `tmp_path` at test time (a `.swift` string with
  class/struct/enum/protocol/extension/func + imports), **NEVER committed under a scanned root**
  (review B1) — exactly like every existing Codas fixture.
- `test_merge_empty_extra_is_identity`: `merge(py_facts, EMPTY)` returns the Python object
  unchanged (review B3) — the byte-identical guarantee by inspection.
- `test_swift_adapter`: symbols (each kind, top-level only, sorted) + imports (target=module,
  target_path=None) from the fixture; skipped on a malformed `.swift`.
- `test_swift_graceful_degrade`: with tree-sitter import forced to fail (monkeypatch), `.swift`
  files → `skipped`, no raise, empty facts.
- `test_byte_identical_python_only`: `symbols()`/`imports()` on a Python-only repo unchanged by
  the merge seam (and the real Codas inventory stays byte-identical — run twice + vs pre-change).
- `test_merge_orders_deterministically`: mixed py+swift facts sort stably.
- Full suite + `codas check` 0 + `agents`/`wiki --verify` clean.

## 10. Design review — APPROVE-WITH-CHANGES (folded 2026-06-22)

Adversarial review (Claude-native; codex MCP stalled — known-flaky in this repo). Architecture
APPROVED with evidence: schema-neutral facts, scanner extension-agnostic (`.swift` already flows
into `ScanContext.files`, no `.py` allowlist — Q7 confirmed), merge-seam location correct,
`target_path=None` makes `dependency_direction` skip Swift at `dependency_direction.py:42`
(`if edge.target_path is None: continue`) → zero false positives (Q4 confirmed). 3 blockers + 4
nits folded above:

- **B1 → §7/§8**: never commit a `.swift` fixture (Codas scans `roots:["."]` incl. `tests/`;
  zero committed non-`.py` there today) — use `tmp_path`.
- **B2 → §7**: Swift-repo inventory determinism requires the `swift` extra installed uniformly;
  mixed envs diverge. Documented operational rule.
- **B3 → §3/§8**: empty-extra merge is an EARLY-RETURN of the unchanged Python object + identity
  test; byte-identical by inspection.
- **N1 → §5**: `head_snapshot` is `.py`-only → Swift out of scope for `fact_delta`/`fact_coupling`
  until a Swift HEAD-blob reader; harmless on Codas, a noted Swift-repo gap.
- **N2 → §7**: `kind` opaque except `policy_registry.py:64` (path-gated, Swift-unreachable).
- **N3 → §7**: dup-detection only for `src/`-rooted Swift (`SCOPE_PREFIX="src/"`).
- **N4 → §7**: pin `tree-sitter~=0.23, tree-sitter-swift~=0.7` (verified compatible, ≥3.9, abi3).

Open-question answers: Q1 optional-extra approved (+B2 caveat); Q2 no byte-diff IF early-return
(B3); Q3 build the thin registry (clean home for the early-return + ext filter); Q4 confirmed;
Q5 safe (+N2); Q6 resolved (N4); Q7 confirmed (scanner agnostic).

## 9. Open questions for codex review (RESOLVED — see §10)

1. **Optional-extra + graceful-degrade** — right call vs hard-depending on tree-sitter? Is the
   lazy-import-in-parse the cleanest guard, or should ScanContext probe availability once?
2. **Additive-merge at symbols()/imports()** — does re-sorting the merged list risk ANY
   byte-difference for the Python-only case? (Claim: no, identical sort key → stable.) Stress it.
3. **§6 registry now vs YAGNI** — build the language registry, or inline Swift until a 3rd lang?
4. **Swift `import` semantics** — `target_path=None` for all Swift imports acceptable for the
   thin slice (keeps dependency_direction silent on Swift)? Or record the module name somewhere
   dependency_direction could later use?
5. **`kind` vocabulary expansion** — adding `struct`/`enum`/`protocol`/`extension`/`actor` as
   new `kind` strings: any policy that switches on `kind` (vs treating it opaque)? (Checked:
   duplicate_* use it opaquely.) Confirm.
6. **tree-sitter version pin + py-tree-sitter API** — `tree-sitter>=0.23` vs 0.25 API drift
   (Language(...)/Parser); pin a tested range. requires-python is >=3.9 — confirm the wheels
   cover it.
7. **Where do `.swift` files enter `self.files`?** The scanner (`discover_files`/`filter_to_
   roots`) currently yields all tracked files; confirm `.swift` already flow through (they
   should — the scanner is extension-agnostic; only the Python adapter filtered `.py`).
