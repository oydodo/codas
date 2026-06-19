# Design — call-graph facts (deterministic stdlib-ast)

> **FINAL (implemented): pyan REJECTED, built a stdlib-`ast` extractor.** The pyan
> borrow (below) was implemented and then found to be **nondeterministic across
> processes** — pyan resolves ambiguous calls via id()-ordered Node sets, so the same
> code yields different call edges per run (verified: 4 CLI `inventory` runs → 3
> distinct hashes), violating Codas's byte-identical core invariant. Scoping/hash-seed
> did not fix it. Reversed (confirmed by codex `a0447cf`) to a pure-stdlib `ast`
> resolver in `src/codas/adapters/callgraph.py`: conservative, first-party-only, with
> a `resolution` tag (`direct` | `imported_symbol` | `module_attribute` |
> `self_method`); unresolved/dynamic/builtin calls are dropped (not guessed).
> Deterministic by construction, MIT, zero-dep (no GPL, no optional extra, no 3.11
> venv). Lower fidelity (no MRO/super/dynamic dispatch) — acceptable; determinism is
> the hard requirement. Verified on the repo: 601 edges (direct 301 / imported_symbol
> 295 / self_method 5), `run_check` → all 15 `check_*` policies, byte-identical across
> runs, `codas check .` = 0. 210 tests. The pyan analysis below is kept as the
> rejected-approach record.

---

# Design (rejected) — call-graph facts (pyan adapter, optional extra)

Authority: §11 (adapters isolate ecosystem tools; core gets normalized facts), the
existing `adapters/python.py` (imports/symbols precedent) + the fact-provider seam.
Grounded by a live pyan probe on this repo.

## Why borrow, not build (settled)

Live test (`/tmp/cw-venv`): `pyan.analyzer.CallGraphVisitor(files).uses_edges` gave
2529 edges; `run_check` correctly resolved to all 15 `check_*` policies +
`build_scan_context` + loaders, scope-resolved via ast+symtable (handles
super/MRO/inheritance). Each pyan node exposes everything a fact needs:
`get_name()` (dotted), `filename` (repo-rel), `namespace`, `name`,
`flavor` (FUNCTION/CLASS/METHOD/UNKNOWN), `defined` (bool), `ast_node.lineno`.
First-party filtering is clean: unresolved/builtin targets are `flavor=UNKNOWN,
defined=False` (e.g. `*.str`), real symbols are `defined=True`. Self-building this
quality (lexical scope + inheritance) is real work for no gain — both are
"approximate" (the inherent static-Python limit). pyan is GPL-2.0 (accepted) and
Python-only (fine — it's an adapter; call facts are language-neutral).

## Optional-extra shape (option B — the load-bearing decision)

pyan must NEVER be imported at module top, or `codas inventory`/`check` would require
it. The import is lazy, inside `extract_call_facts`, and absence is graceful:

```python
# src/codas/adapters/callgraph.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CallFact:
    caller_module: str
    caller_symbol: str
    caller_path: str
    caller_line: int
    callee_module: str
    callee_symbol: str
    callee_path: str
    callee_line: int


@dataclass(frozen=True)
class CallFacts:
    edges: tuple[CallFact, ...]
    available: bool          # False when pyan (the `callgraph` extra) is not installed
    skipped: tuple[str, ...]


def extract_call_facts(repo: Path, files: tuple[str, ...]) -> CallFacts:
    """First-party Python call edges via pyan (optional `callgraph` extra).

    Lazy import: when pyan is absent, returns an empty, available=False result so the
    deterministic core runs without the GPL dependency. Keeps only edges where both
    endpoints are first-party (`defined`), dropping builtins/unresolved (`*.x`).
    Deterministic (stable sort); pyan's ast analysis is reproducible for given files.
    """
    py = tuple(f for f in files if f.endswith(".py"))
    try:
        from pyan.analyzer import CallGraphVisitor
    except ImportError:
        return CallFacts(edges=(), available=False, skipped=("pyan-not-installed",))

    abs_files = [str(repo / f) for f in py]
    visitor = CallGraphVisitor(abs_files, root=str(repo))   # explicit root -> stable names
    seen: set = set()
    edges: list[CallFact] = []
    for caller, callees in (visitor.uses_edges or {}).items():
        if not getattr(caller, "defined", False):
            continue
        for callee in callees:
            if not getattr(callee, "defined", False):
                continue
            fact = _to_fact(repo, caller, callee)
            if fact is None:
                continue
            key = (fact.caller_path, fact.caller_symbol, fact.callee_path, fact.callee_symbol)
            if key in seen:
                continue
            seen.add(key)
            edges.append(fact)
    edges.sort(key=lambda e: (e.caller_path, e.caller_symbol, e.callee_path, e.callee_symbol))
    return CallFacts(edges=tuple(edges), available=True, skipped=())
```

`_to_fact` converts pyan nodes → repo-relative paths (drop anything whose filename
isn't under the repo / not a scanned file), reading `namespace`, `name`, `filename`,
`ast_node.lineno`. (The probe showed `filename` already repo-relative when relative
paths are passed; passing absolute + `root=repo` is more robust — confirm the
relativization in impl.)

## Inventory: `structure/inventory.py`

```python
from codas.adapters.callgraph import extract_call_facts
...
call_facts = extract_call_facts(repo, tuple(files))
inventory["calls"] = {
    "available": call_facts.available,
    "sources": sorted({e.caller_path for e in call_facts.edges}),
    "edges": [
        {"caller_module": e.caller_module, "caller_symbol": e.caller_symbol,
         "caller_path": e.caller_path, "caller_line": e.caller_line,
         "callee_module": e.callee_module, "callee_symbol": e.callee_symbol,
         "callee_path": e.callee_path, "callee_line": e.callee_line}
        for e in call_facts.edges
    ],
    "skipped": list(call_facts.skipped),
}
```

Block always present (carries `available: false` + empty edges when pyan absent) so
the inventory schema is stable regardless of the extra.

## Seam: `facts/context.py`

Memoized `calls()` accessor + re-export `CallFact`/`CallFacts` via `__all__`. The
seam importing `adapters.callgraph` is safe — that module does not import pyan at top.

## Determinism / dogfooding

- Deterministic **within an environment**: sorted edges, pyan's ast analysis is
  reproducible. The `calls` block DOES differ between a pyan-present env (populated)
  and a pyan-absent env (`available:false`, empty) — acceptable for an optional extra;
  byte-identical across two runs in the same env. **The repo's own dogfood gate runs
  in the 3.11+ pyan venv**, so its reference `calls` block is populated.
- Facts-only: no policy added → `codas check . = 0`. New `adapters/callgraph.py` sits
  under the owned `codas-adapters` unit → no `unowned` growth.
- New public symbols `CallFact`/`CallFacts`/`extract_call_facts` unique under `src/`;
  no new top-level private helper name collisions (verify `_to_fact`).
- GPL confinement: pyan imported only inside the optional adapter, only when the
  `callgraph` extra is installed. Core distribution stays MIT + pyyaml-only.

## Dev environment

`python3` on this box is 3.9 (below pyan's >=3.10 and Codas's pyproject >=3.11).
Create a project venv: `python3.14 -m venv .venv && .venv/bin/pip install -e
.[callgraph]` (or `pip install pyyaml pyan3`). The dogfood gate becomes
`.venv/bin/python -m unittest discover -s tests` + `.venv/bin/python -m codas check .`.
Document in AGENTS.md / README. (The 3.9 runs were always off-spec vs pyproject
>=3.11; this just makes the supported runtime real.)

## Tests (`tests/test_call_facts.py`)

- **pyan present** (skip if `import pyan` fails, so the suite still passes without the
  extra): `extract_call_facts` on a small fixture package (a calls b, b calls c) →
  expected first-party edges with correct paths/lines; a builtin/undefined call is
  dropped; two calls return equal results.
- **pyan absent**: monkeypatch the import (or a thin seam) to raise ImportError →
  `available=False`, empty edges, no exception.
- **inventory**: `calls` block present; `available` reflects env.
- **check stays 0** (facts-only).
- Real-repo smoke (pyan venv): `calls` populated, has `run_check -> check_*` edges,
  byte-identical twice.

## Open questions for codex design review

1. **Optional-extra shape** — lazy import + `available` flag + always-present empty
   block. Right? Or omit the block entirely when pyan absent (schema instability)?
2. **Env-dependent inventory** — the `calls` block differs pyan-present vs absent.
   Acceptable for an optional extra (byte-identical within an env)? Should the repo's
   reference/dogfood explicitly require the extra so `calls` is always populated here?
3. **First-party filter** — `defined == True` on both endpoints (drops UNKNOWN /
   builtins / `*.x`). Complete + correct, or also gate on `filename` under repo? Any
   first-party edge wrongly dropped (e.g. `__init__` re-exports, decorators)?
4. **`root` handling** — `CallGraphVisitor(abs_files, root=str(repo))` for stable
   module names + to silence the `infer_root` warning. Correct root (repo vs `src`)?
   The probe got correct names even without root — confirm with `root`.
5. **Fact shape** — full (module+symbol+path+line both ends) vs compact. Keep line on
   both ends (useful for impact/preflight evidence)?
6. **Scope** — `uses` edges only (calls), defer `defines`/`recursion`. Include test
   files (callers in tests are useful for the later test-coverage policy) — keep them?
7. **Dev-env / gate change** — fold the venv + AGENTS.md/README gate update into this
   task, or a separate setup task? (It is a prerequisite to run the new tests.)
8. **GPL** — importing pyan (when the extra is installed) inside the adapter: any
   license note needed in pyproject / NOTICE, given Codas core is MIT?
