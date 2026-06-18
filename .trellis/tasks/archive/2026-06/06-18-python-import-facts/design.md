# Design — P3 B1: Python import facts

Authority: `docs/codas-implementation-plan.html` §11 (Python adapter: imports →
reference facts), §6 (facts neutral/complete/deterministic), §5 inventory schema.

## Dataclasses (`adapters/python.py`)

```python
@dataclass(frozen=True)
class ImportFact:
    module: str        # importer, repo-relative .py path
    target: str        # absolute dotted module name imported
    target_path: str | None  # repo-rel path of target if first-party, else None
    line: int

@dataclass(frozen=True)
class ImportFacts:
    imports: tuple[ImportFact, ...]
    skipped: tuple[str, ...]
```

## File → dotted module map (first-party resolution, no hard-coded `src/`)

A directory is a package iff it contains `__init__.py`. From the scanned `files`:

```
package_dirs = { dirname(f) for f in files if f == "__init__.py" or f.endswith("/__init__.py") }
```

`dotted_for(path)`: walk up from the file's directory while each dir is in
`package_dirs`, collecting basenames; reverse → package prefix. Module = prefix
for an `__init__.py`, else prefix + `.` + stem.

- `src/codas/policies/stale_claim.py` → `codas.policies.stale_claim` (stops at
  `src`, which has no `__init__.py`).
- `src/codas/facts/__init__.py` → `codas.facts`.

`module_paths: dict[str, str]`: built over **`sorted(files)`** with `setdefault`,
so if two files collapse to the same dotted name (e.g. non-package files outside
any `__init__.py` chain that reduce to a bare stem) the lexicographically-first
path wins — deterministic, never dict-ordering-dependent. (Within a real package
layout, dotted names are unique; the collision rule only matters for stray
non-package files, see Limitations.)

## Relative-import resolution

Importer module `M = dotted_for(path)`. Its package
`pkg = M if path is __init__ else M.rpartition(".")[0]`. Mirror CPython:

```
def _resolve_import(module, level, pkg):     # -> str | None  (renamed to avoid a
                                              # duplicate_implementation collision
                                              # with markdown._resolve)
    if level == 0:
        return module
    parts = pkg.split(".") if pkg else []
    if level - 1 > len(parts):          # relative import escapes the top package
        return None                     # CPython raises ImportError; we mark unresolvable
    base = ".".join(parts[: len(parts) - (level - 1)])
    if not base:
        return module or None
    return f"{base}.{module}" if module else base
```

`_resolve_import` returns `None` when the relative import climbs above the top package
(`pkg.rsplit` would silently mis-resolve instead of mirroring CPython's
ImportError). A `None` resolution emits no edge for that statement — it cannot be
first-party. Real code in this repo never escapes; the guard is robustness.

## Edge emission (per `.py`, `ast.walk`)

- `import a.b, c` → targets `a.b`, `c` (full dotted alias names).
- `from M import n1, n2` (M = `_resolve(node.module, level, pkg)`):
  - if `node.module is not None`: emit target `M` (the module imported from).
  - for each name `n`: `dotted = f"{M}.{n}"` (or `n` if M empty); emit **only if**
    `dotted in module_paths` — captures `from pkg import submod` /
    `from .. import adapters` as a first-party submodule edge, without polluting
    facts with `pkg.mod.SymbolName` (a class/func name never resolves to a path).

For each emitted target dotted name, `target_path = module_paths.get(dotted)`
(None ⇒ external/stdlib). Dedup `(module, target, line)`; sort
`(module, line, target)`. Unparseable file → `skipped` (same gate as
`extract_symbol_facts`).

Worked: `from codas.adapters.python import SymbolFact` → target
`codas.adapters.python` (first-party path); the name `SymbolFact` does not resolve
→ not emitted. `from .. import adapters` in `codas.policies.X` → `M=codas` (no
`node.module` ⇒ base only), name `adapters` → `codas.adapters` ∈ module_paths →
emitted with its path. `import os` → `os`, target_path None.

## Inventory block (`structure/inventory.py`, after `symbols`)

```python
imports = extract_import_facts(repo, tuple(files))
inventory["imports"] = {
    "sources": sorted({fact.module for fact in imports.imports}),
    "edges": [
        {"module": f.module, "target": f.target,
         "target_path": f.target_path, "line": f.line}
        for f in imports.imports
    ],
    "skipped": list(imports.skipped),
}
```

This is the legit adapter→facts bridge (inventory already imports the python
adapter). No `ScanContext.imports()` accessor yet (B2 adds it with its consumer).

## Determinism / dogfooding

- Sorting is total `(module, line, target)`; `module_paths` is a pure function of
  the sorted file set; resolution is deterministic. Inventory byte-identical x2.
- No new module/governance file → no `structure.yml`/`config.yml`/`documents.yml`
  change. `check .` stays 0 (B1 adds a fact only; no policy consumes it yet).
- Note: the inventory size grows (new block) — expected; the invariant is
  *byte-identical across two runs*, not constant size.

## Tests (`tests/test_python_adapter.py` extend, or new `test_python_import_facts.py`)

- absolute `import a.b` / `from a.b import c`; relative `from . import x`,
  `from ..pkg import y`, bare `from .. import pkg`; `__init__.py` package module;
  external `import os` → target_path None; name that is a symbol (not submodule)
  not emitted as a phantom edge; dedup + total sort; unparseable → skipped.

## Limitations (documented)

- **Namespace packages** (PEP 420, no `__init__.py`) are not recognized — a dir is
  a package only if it has `__init__.py`. All Codas packages have one, so this is a
  non-issue here; flagged for non-`src/codas` layouts.
- **Non-package `.py` files** (no `__init__.py` chain) collapse to a bare stem
  module name and may collide; `module_paths` keeps the sorted-first path
  deterministically. These files are not import *targets* of governed code, so the
  collision is inert for the B2 boundary policy.

## Open questions for codex design review

- Edge model: emit module-level target (`pkg.mod`) + first-party submodule names
  only — does this capture every dependency edge a structure-unit policy (B2)
  needs, without phantom symbol-name edges? Any import form missed (star imports
  `from x import *` → name `*`, never a module → only base `x` emitted; correct)?
- `dotted_for` package-chain walk vs a configured source root — is the
  `__init__.py` walk robust for namespace packages (no `__init__.py`)? For this
  repo all packages have `__init__.py`; flag namespace-package handling as a known
  limitation if relevant.
- Should external imports be emitted at all (completeness) or filtered to
  first-party (smaller fact)? Current: emit all; B2 filters.
