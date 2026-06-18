# PRD — P3 B1: Python import facts

## Context

P3 §11 Adapter Boundary. A1/A2 removed direct adapter imports from policies via
`ScanContext`. The boundary is now guarded only by an interim unit test
(`test_no_policy_imports_an_adapter`). B2 will turn that into a dogfooded Codas
finding — a *dependency-direction* policy that reads `structure.yml`
`dependency_rules` and reports a module that imports a forbidden unit. That policy
needs a **fact**: which module imports which. This slice (B1) produces it.

§11 Python adapter — "Allowed to know: modules, classes, functions, **imports**,
pyproject" → "Must emit: symbol facts, **package facts**". The adapter currently
emits only symbol definitions. B1 adds import (reference) facts.

## Goal

The Python adapter emits `ImportFacts`: for every tracked `.py`, the modules it
imports, each resolved to an absolute dotted name and — when first-party — to the
repo-relative path of the imported module. Surface them as a deterministic
`imports` block in `codas inventory`.

## Requirements

1. `extract_import_facts(repo, files) -> ImportFacts` in `adapters/python.py`.
   - `ImportFact{module: str (importer repo-rel .py), target: str (absolute dotted),
     target_path: str | None (repo-rel path if the target resolves to a scanned
     module, else None), line: int}`.
   - Resolve relative imports (`from . / .. import x`) against the importer's
     package. Map file→dotted module by walking the `__init__.py` package chain
     (no hard-coded `src/` prefix).
   - Emit module-level edges: `from pkg.mod import Name` → target `pkg.mod`
     (NOT `pkg.mod.Name`); `from pkg import submod` / `from .. import adapters` →
     also emit the first-party submodule edge `pkg.submod` so package-relative
     imports are captured. External/stdlib imports are emitted with
     `target_path=None` (facts stay complete, not just first-party).
   - Deterministic: dedup, sort by `(module, line, target)`. Unparseable files →
     `skipped`.
2. `codas inventory` gains an `imports` block `{sources, edges, skipped}` after
   `symbols`, byte-identical across runs.

## Acceptance criteria

- `extract_import_facts` resolves: absolute (`import a.b`, `from a.b import c`),
  relative (`from . import x`, `from ..pkg import y`, bare `from .. import pkg`),
  and `__init__.py` package modules; first-party targets carry `target_path`,
  external carry `None`.
- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings".
- `codas inventory . --json` byte-identical across two runs; new `imports` block
  present.
- Full suite green; new adapter unit tests cover each import form + resolution.

## Non-goals

- The dependency-direction *policy* + `structure.yml`
  `codas-policies: must_not_depend_on: [codas-adapters]` rule — B2 (B1 is
  facts-only; no new policy, no findings).
- Package/pyproject facts beyond imports — not needed for the boundary policy.
- Symbol *usage* / call-graph facts — out of scope.
- A `ScanContext.imports()` accessor — added in B2 when its consumer (the policy)
  exists; B1 wires the adapter only into `build_inventory` (the legit bridge).
