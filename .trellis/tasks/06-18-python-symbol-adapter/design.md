# Design: Python symbol adapter (symbol facts)

## Adapter (`src/codas/adapters/python.py`)

Mirrors `adapters/trellis.py`: frozen dataclasses, a `skipped` list for
unparseable inputs, deterministic sort, no raising.

```
@dataclass(frozen=True)
class SymbolFact:
    module: str   # repo-relative .py path
    name: str
    kind: str     # "class" | "function"
    line: int

@dataclass(frozen=True)
class SymbolFacts:
    definitions: tuple[SymbolFact, ...]
    skipped: tuple[str, ...]

def extract_symbol_facts(repo: Path, files: tuple[str, ...]) -> SymbolFacts:
    defs: list[SymbolFact] = []
    skipped: list[str] = []
    for rel in sorted(f for f in files if f.endswith(".py")):
        try:
            source = (repo / rel).read_text(errors="ignore")
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            skipped.append(rel)
            continue
        for node in tree.body:                      # top-level only
            if isinstance(node, ast.ClassDef):
                defs.append(SymbolFact(rel, node.name, "class", node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.append(SymbolFact(rel, node.name, "function", node.lineno))
    defs.sort(key=lambda d: (d.module, d.line, d.name, d.kind))
    return SymbolFacts(tuple(defs), tuple(sorted(skipped)))
```

Notes:
- `ast.parse` raises `SyntaxError` (and `ValueError` for null bytes); both →
  `skipped`. `errors="ignore"` on read so odd encodings never raise.
- `tree.body` is direct module-level nodes only — methods (inside ClassDef),
  nested funcs, and defs inside `if/try` blocks are intentionally NOT walked
  (non-goal). This keeps the first-cut signal = top-level type/function names.
- `kind` collapses `AsyncFunctionDef` → `"function"`; duplicate detection cares
  about the name collision, not async-ness.
- Sort key `(module, line, name, kind)` is total within a module (two defs cannot
  share a line); across modules `module` disambiguates. Deterministic.

## Inventory wiring (`src/codas/structure/inventory.py`)

After the existing `tasks` block, add (same shape as `doc_claims` / `tasks`):
```
symbols = extract_symbol_facts(repo, tuple(files))
inventory["symbols"] = {
    "sources": sorted({d.module for d in symbols.definitions}),
    "definitions": [
        {"module": d.module, "name": d.name, "kind": d.kind, "line": d.line}
        for d in symbols.definitions
    ],
    "skipped": list(symbols.skipped),
}
```
`files` is the already-discovered, root-filtered list build_inventory holds.
`sources` lists only modules that actually contributed a definition (an empty or
import-only `.py` contributes nothing and is absent from `sources` but, if
unparseable, present in `skipped`).

## Determinism

- Input `files` is sorted; `.py` filter preserves order; `defs` re-sorted on a
  total key; `sources`/`skipped` sorted. No timestamps, no randomness, no AST
  field that varies by run (`lineno` is source-derived). → byte-identical
  inventory across runs (verify with the 2x diff).

## check.py

Untouched — no policy consumes symbols this slice, so `codas check .` stays at 0
findings. (The duplicate policy is the next slice; it will also have to scope out
benign cross-module duplicates such as the shared test helpers `_write`,
`_config`, `_unit` that this fact layer will surface — a next-slice concern, noted
so it is not a surprise.)

## Tests (`tests/test_python_adapter.py`)

Unit tests over a temp repo (no git needed; pass an explicit `files` tuple):
- top-level `class Foo:` and `def bar():` → two SymbolFacts, correct kind/line.
- `async def baz():` → kind `"function"`.
- method inside a class and a nested function → NOT emitted (top-level only).
- a `.py` with a syntax error → in `skipped`, not `definitions`, no raise.
- a non-`.py` file in the input → ignored.
- determinism: two modules with same-named symbol → both present, sorted by
  `(module, line, name, kind)`.
- empty / import-only module → no definitions, not skipped.

Plus an inventory integration assertion in `tests/test_inventory.py`: the
`symbols` block exists, contains a known Codas symbol (e.g. a `build_inventory`
function fact), and the inventory is byte-identical across two `build_inventory`
calls (determinism guard for the new block).

## Dogfooding checklist

- New concept surfaced: Python **symbol facts** (a Fact, per §6/§11). It is a
  fact layer, not a behavior/claim change to existing policies → no policies.yml
  edit. The adapter realizes the §11 Python-adapter row ("Must Emit: symbol
  facts") — already an authoritative claim, so no plan/schema edit needed.
- New artifacts: `src/codas/adapters/python.py` (governed by `codas-adapters`
  unit) and `tests/test_python_adapter.py` (governed by `codas-tests`). No new
  module directory → no structure.yml unit edit; `inventory.unowned` stays empty.
- Bootstrap gate: `unittest discover` + `git status --short` clean.
- Link `program:P2:policy-engine-structure-drift` → this task (symbol-facts
  groundwork for `duplicate_implementation`).
