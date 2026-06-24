# Design — tree-sitter gate adapter (Swift first language)

Gate-semantics (touches fact extraction → the byte-identical inventory) → codex DESIGN review
before impl. Worktree `harness-tree-sitter-gate-adapter` / `feat/tree-sitter-gate-adapter`.

**Reuses** the codex-reviewed archived design `.trellis/tasks/archive/2026-06/06-22-swift-extraction/design.md`
(APPROVE-WITH-CHANGES, B1-B3 + N1-N4 folded). This doc carries that design forward and records
**two material corrections found by validating against the REAL installed grammar** (§A, §B) —
do not trust the archived design's guessed node kinds or version pin.

## A. CORRECTION 1 — dependency pin + Python floor (supersedes archived N4)

The archived pin `tree-sitter~=0.23, tree-sitter-swift~=0.7` is **INCOMPATIBLE**. Verified live:
- `tree-sitter-swift` ships only `0.7.2 / 0.7.3` (+ ancient 0.0.1); both emit grammar **ABI 15**.
- ABI 15 needs `tree-sitter >= 0.24`. On **Python 3.9** the newest wheel is `tree-sitter 0.23.2`
  (ABI ≤14) → `ValueError: Incompatible Language version 15. Must be between 13 and 14`.
- Validated working combo: **Python 3.12 + tree-sitter 0.25.2 + tree-sitter-swift 0.7.3**.

**Decision**: Codas CORE stays `requires-python >= 3.9`, `pyyaml`-only. The **optional `codas[swift]`
extra requires Python ≥3.10** (`tree-sitter>=0.24`, `tree-sitter-swift~=0.7`). Dev/test of this
task uses a Python 3.12 venv (`/tmp/codas-ts312`, outside the repo so it is never scanned). The
full existing suite must be confirmed green under 3.12 before merge (the dev-env bump is safe).

## B. CORRECTION 2 — real Swift node grammar (supersedes archived §4 node kinds)

Validated against tree-sitter-swift 0.7.3. The archived design's `struct_declaration` /
`enum_declaration` / `extension_declaration` node types **DO NOT EXIST**. Real grammar:

| Swift decl | node type | how to read |
| --- | --- | --- |
| class / struct / enum / extension / actor | **all `class_declaration`** | `kind` = the leading ANON keyword child (`class`/`struct`/`enum`/`extension`/`actor`); name = `child_by_field_name("name")` (works with modifiers, e.g. `public final class B`) |
| protocol | `protocol_declaration` | name field |
| func | `function_declaration` | name field |
| typealias | `typealias_declaration` | name field |
| top-level let/var | `property_declaration` | EXCLUDED (mirror Python: module-level vars are not symbols) |
| import | `import_declaration` | target = the single named child's dotted text (`Foundation`, `UIKit.UIView`) |

**Extensions are EXCLUDED from symbols** (correction): `extension A` has `name="A"` — it reuses
the extended type's name, so emitting it as a symbol would create a false `duplicate_symbol` /
`duplicate_implementation` against `class A`. Extensions define no new top-level name. (The
archived design wrongly listed `extension` as a symbol kind.)

Symbol kinds emitted: `class` `struct` `enum` `actor` `protocol` `function` `typealias`
(all opaque strings to policies — confirmed below). Top-level only (open-world lower bound).

## 1. Extraction seam (re-verified @ main b98d937 — unchanged from archived §1)
- `facts/context.py`: `_parsed()` (138) → `symbols()` (149) / `imports()` (155) / `calls()` (170).
- `adapters/python.py`: `SymbolFact(module,name,kind,line)` + `SymbolFacts(definitions,skipped)`;
  `ImportFact(module,target,target_path,line)` + `ImportFacts(imports,skipped)`. A parse failure
  routes the file to `skipped`, never raises (python.py:64/73) — the graceful-degrade precedent.
- `pyproject.toml` deps: `pyyaml>=6.0` only (tree-sitter is the FIRST native dep → optional extra).

## 2. Dependency strategy — optional extra + graceful degrade (archived §2, pin per §A)
- `pip install codas[swift]` → `tree-sitter>=0.24, tree-sitter-swift~=0.7`; `requires-python` for
  the extra ≥3.10. Core install pulls nothing new.
- `adapters/swift_parse.py` imports tree-sitter **lazily inside the parse fn**, guarded: import
  fails (extra absent) OR no `.swift` files → no-op returning EMPTY facts, `.swift` paths → skipped.
  Also guard the ABI `ValueError` (an env with tree-sitter<0.24 + swift 0.7) → treat as unavailable
  (degrade, not crash) — concrete because of §A.
- **pyproject mechanism (codex NIT 1)**: `[project.optional-dependencies] swift = ["tree-sitter>=0.24",
  "tree-sitter-swift~=0.7"]`. PEP 508 cannot pin `requires-python` per-extra, so do NOT use an
  env-marker dep that silently no-ops on 3.9 — let `tree-sitter>=0.24` FAIL pip resolution cleanly
  on 3.9 (honest error). AND: when `.swift` files are present but the extra is unavailable, emit
  ONE explicit "Swift extraction unavailable — install codas[swift] on Python ≥3.10" notice (not a
  silent degrade) so a 3.9 user knows their `.swift` is unscanned. The notice must be
  out-of-inventory (a stderr/log line, never a fact) to keep byte-identical.
- Open-world invariant ([[codas-perception-model]]): missing parser = fewer facts, never a denial.

## 3. Additive-merge seam — byte-identical BY CONSTRUCTION (archived §3, B3)
`symbols()`/`imports()` merge Python facts with `extract_language_symbols/imports(repo, files)`.
`_merge_symbol_facts(py, extra)` **EARLY-RETURNS the unchanged Python object when extra is empty**
(byte-identical by inspection, not by a sort-stability argument). Non-empty → concat + re-sort by
the SAME key (`(module,line,name,kind)`; imports `(module,line,target)`). `calls()` UNCHANGED
(Swift contributes no call edges — thin slice). Identity test: `merge(py, EMPTY) is py`.

## 4. Modules
- `adapters/swift_parse.py` — **CONTENT-first core** `parse_swift_sources(sources: dict[path,
  content]) -> ParsedSwiftModules` (lazy tree-sitter; ABI-fail/parse-error → skipped) + a thin
  disk wrapper `parse_swift_modules(repo, files)` that reads `.swift` bytes then calls the core.
  The content core is SHARED by the working-tree scan AND `head_snapshot` (which feeds it git blob
  content), so both delta sides parse Swift identically (§5.1).
- `adapters/swift.py` — `extract_swift_symbols(parsed) -> SymbolFacts`,
  `extract_swift_imports(parsed) -> ImportFacts` (reuse the language-neutral SymbolFact/ImportFact).
  Symbols per §B; imports `ImportFact(module=<.swift path>, target=<dotted module>, target_path=None,
  line)`. `target_path=None` always (Swift module→file = SPM/Xcode map, DEFERRED) →
  `dependency_direction` skips Swift (`if edge.target_path is None: continue`) → zero false positives.
- `facts/languages.py` — thin registry: `LanguageExtractor(name, extensions, symbols, imports)`;
  `LANGUAGES=(SWIFT,)`; `extract_language_symbols/imports` union over LANGUAGES; and a
  `LANGUAGE_EXTENSIONS` tuple (union of each `extensions`) that `list_paths_at_head` consumes (§5.1)
  so the HEAD lister auto-covers every registered language. Python NOT folded in (keep the proven
  stdlib path untouched, minimal blast radius).

## 5. Deferred (placed, not built) — unchanged from archived §5
Swift call-graph (no CST type resolution); Swift dependency_direction (needs module map);
member-level symbols (top-level first); `ciri` adoption; CodeGraph advisory adapter (task ②, the
advisory tier this gate-grade slice complements). Swift fact_delta/fact_coupling → see §5.1 (now
a RESOLVED design clause, not just "deferred").

## 5.1. fact_coupling symmetry — SYMMETRIC BY CONSTRUCTION (codex BLOCKER 7, option (a))

The codex blocker: the merge lands in `symbols()`/`imports()`, `working_snapshot()` (context.py:282)
builds from those merged accessors, but `head_snapshot()` (context.py:295 → snapshot.py:57) reads
`.py` blobs ONLY (`list_python_paths_at_head`, git.py:87 `endswith(".py")`). Working carries Swift,
HEAD does not → `fact_delta` reports every Swift fact as permanently "added" → `check_fact_coupling`
(always run, check.py:76) FALSE-GATES on every clean `codas check` in a Swift repo.

**Resolution = make BOTH snapshots language-symmetric (not exclude Swift from the delta).** A
generalized HEAD lister + a symmetric HEAD parse/merge so Swift appears on BOTH sides; the delta is
then a real py+swift diff. This DISSOLVES the blocker (symmetric by construction — no working-side
special case) and makes Swift a first-class gate-delta language.

- **`list_python_paths_at_head` → `list_paths_at_head(repo, extensions)`** (git.py): the only
  language-specific line is the `endswith(".py")` filter → `endswith(extensions)` (`str.endswith`
  accepts a tuple). `extensions` = the REGISTERED-language set `(".py",) + LANGUAGE_EXTENSIONS`
  (from `facts/languages.py`). **NOT "all blobs"** — a non-source blob (`.md`/`.yml`) must never
  enter the snapshot or it changes `skipped` and breaks byte-identical.
- **`read_blob_at_head`** is already generic (reads any blob by sha) — unchanged.
- **`head_snapshot` (snapshot.py) routes by extension + merges**: split the listed blobs by ext,
  parse `.py` via `parse_sources` and `.swift` via `parse_swift_sources` (the CONTENT-first Swift
  core, §4), then merge the two FactSnapshots with shared merge helpers in `codas.facts.snapshot` (or a neutral
  `codas.facts.merge` helper module), not helpers owned by `ScanContext`/`context.py`. This avoids a
  reverse dependency from `snapshot.py` back into `context.py`; `working_snapshot` and `head_snapshot` both
  call the same neutral merge path. `working_snapshot` keeps using the merged `symbols()`/`imports()`/
  `calls()` (no change). Both sides now = merge(python, swift).
- **Byte-identical on Codas**: zero `.swift` → `endswith((".py",".swift"))` returns the IDENTICAL
  `.py` set; the Swift parse yields EMPTY; the merge early-returns the Python FactSnapshot
  unchanged → both snapshots byte-identical to today → `fact_delta` unchanged. Proven by the
  existing fact-delta tests staying green + run-twice.
- **Swift IS in the gate delta**: a Swift symbol rename across commits now shows in `fact_delta`
  deterministically (tree-sitter is gate-grade, in-core — unlike CodeGraph, which is advisory and
  can NEVER feed this gate). `fact_coupling` can gate a declared Swift coupling. (No Swift coupling
  is declared in `.codas/claims.yml` today, so the machinery is exercised by a synthetic test, but
  it is correct + symmetric — not deferred.)
- Test: `test_head_snapshot_multilang_symmetric` — a `tmp_path` git repo with a committed `.swift`
  file: `head_snapshot` contains the Swift symbol; after a working-tree Swift rename, `fact_delta` shows the old Swift symbol in `symbols_removed` and the new Swift symbol in `symbols_added` (not a spurious "all Swift facts added"); and on a Python-only repo `fact_delta` is unchanged
  vs the pre-change baseline (byte-identical). (skipUnless tree-sitter for the Swift assertions.)

## 6. Gate-semantics & invariants (archived §7, all still hold)
- **Byte-identical**: Codas has zero `.swift` → empty extra → §3 early-return → inventory
  unchanged. Test: inventory hash before/after seam == ; `symbols()`/`imports()` snapshot on a
  Python-only fixture unchanged; run-twice.
- **B1 (CRITICAL)**: NEVER commit a `.swift` fixture — Codas scans `roots:["."]` incl. `tests/`,
  scanner is extension-agnostic (the `.py` filter is adapter-only), so a committed `.swift` enters
  Codas's OWN inventory and moves the hash. Swift fixtures = `tmp_path` at test time, like every
  existing fixture.
- **B2**: a Swift repo's inventory depends on whether `codas[swift]` (and ABI-compatible
  tree-sitter) is installed → present = real facts, absent = `.swift` in `skipped`. Both
  deterministic, but MIXED envs diverge → operational rule: any env running `codas check` on a
  Swift repo installs `codas[swift]` on Python ≥3.10. Codas itself immune (zero `.swift`).
- **`kind` opaque to policies EXCEPT `policy_registry.py:64`** (switches on `kind=="function"`,
  path-gated to `src/codas/policies/` + `check_` prefix → a Swift `func` can't reach it). Safe.
- **dup-detection** only for `.swift` under `src/` (`SCOPE_PREFIX="src/"`); a `Sources/`-layout
  repo gets none (later scope-config concern).
- **ownership/§11**: `adapters/swift*.py` → `codas-adapters`, `facts/languages.py` → `codas-facts`
  (imports `adapters/swift`, same direction `facts`→`adapters` already allowed). Unique top-level
  names (`extract_swift_symbols`, not `extract_symbol_facts*`) avoid the name-collision gate.
- **Determinism**: tree-sitter parse deterministic; sort all outputs; no dict-order leakage.

## 7. Test plan (archived §8 + the §A/§B corrections)
- All Swift-extraction tests run under the 3.12 venv; the LIVE-parse tests `skipUnless` an
  ABI-compatible tree-sitter is importable (so the 3.9 core suite stays green, degrade-tested).
- `test_merge_empty_extra_is_identity`: `merge(py, EMPTY) is py` (no-tree-sitter; B3).
- `test_byte_identical_python_only`: `symbols()`/`imports()` on a Python-only repo unchanged by
  the seam; Codas inventory run-twice + vs pre-change (no-tree-sitter).
- `test_swift_graceful_degrade`: tree-sitter import/ABI forced to fail (monkeypatch) → `.swift` →
  skipped, no raise (no-tree-sitter).
- `test_swift_adapter` (skipUnless tree-sitter): each kind via the keyword-child path
  (class/struct/enum/actor/protocol/function/typealias), extensions EXCLUDED, top-level only,
  sorted; imports target=dotted module, target_path=None; malformed `.swift` → skipped. Fixtures
  via `tmp_path`.
- `test_merge_orders_deterministically`: mixed py+swift facts sort stably (skipUnless).
- `test_list_paths_at_head_extensions`: `list_paths_at_head(repo, (".py",".swift"))` on a committed
  fixture returns both; with `(".py",)` returns only `.py`; never returns `.md`/`.yml` (no-tree-sitter).
- `test_head_snapshot_multilang_symmetric` (§5.1, skipUnless tree-sitter): committed `.swift` →
  `head_snapshot` carries the Swift symbol; a working rename shows as old-symbol removed + new-symbol added, not
  "all Swift facts added"; Python-only repo `fact_delta` unchanged vs pre-change baseline.
- Full suite under 3.12 + `codas check` 0 + `wiki --verify` / `agents --verify` clean +
  byte-identical 2×.

## 8a. codex DESIGN review outcome (a0f558748, 2026-06-23) + revision

**Round 1 verdict: NEEDS-REWORK** — 1 BLOCKER + 6 NITs.
- **BLOCKER 7 (fact_coupling symmetry)** → see §5.1. **Resolution PIVOTED (user direction) from
  option (b) "exclude Swift from the delta / working_snapshot Python-only" to option (a) "generalize
  `list_python_paths_at_head` → `list_paths_at_head(extensions)` + symmetric HEAD parse/merge"** —
  Swift becomes a first-class gate-delta language (symmetric by construction), no working-side
  special case. tree-sitter is gate-grade (in-core, deterministic) so it MAY feed the gate delta,
  unlike CodeGraph (advisory). Cost: trivial lister generalization + ~30-line head_snapshot routing,
  reusing the same `_merge_*` functions.
- NIT 1 (pyproject mechanism) → folded into §2 (clean pip-fail on 3.9 + explicit unavailable notice).
- NITs 2-6 → all CLEAN confirmations (extension-exclusion correct vs duplicate_*.py:29/37/51/59;
  early-return identity sound vs python.py sort keys; target_path=None skips dependency_direction.py:40-42;
  kind opaque except policy_registry.py:64 path-gated; byte-identical-under-3.12 evidence sufficient).

**Round 2 verdict: APPROVE-WITH-CHANGES** — option (a) is accepted: generalized HEAD listing +
symmetric HEAD parse/merge eliminates the Swift false-gate blocker. Two changes folded before impl:
- merge helpers must live in `codas.facts.snapshot` or a neutral `codas.facts.merge`, never in
  `context.py`, so `snapshot.py` does not depend back on `ScanContext`; §5.1 now states this.
- tests must assert added/removed symbol keys, not a synthetic rename event; §5.1 and §7 now state
  old Swift symbol removed + new Swift symbol added, and explicitly not "all Swift facts added".

## 8b. Original open questions for codex DESIGN review (answered in 8a)
1. §A: confirm CORE stays ≥3.9 and only the extra requires ≥3.10 (vs bumping the whole project to
   ≥3.10 now). Is "extra-only floor" expressible/clean in pyproject, or does it need a runtime guard?
2. §B: excluding `extension` from symbols — agreed (avoids false dup), or should an extension be a
   distinct fact kind that dup-detection is taught to ignore? (I say exclude — simplest, sound.)
3. The registry (§4) now vs YAGNI inline-Swift until a 3rd language? (~15 lines, makes the merge
   language-blind; archived review said build it.)
4. ABI `ValueError` caught as "unavailable" (degrade) — right, or should it surface as a louder
   config error so a mis-pinned env isn't silently degraded on a Swift repo?
5. Any byte-identical / dogfooding trap from the dev-env bump to 3.12 (e.g. dict-ordering, hash,
   stdlib-ast output differences between 3.9 and 3.12 that would move the committed inventory)?
   — this is the one I most want stressed: does running `codas wiki --write` under 3.12 produce
   byte-identical output to 3.9?
