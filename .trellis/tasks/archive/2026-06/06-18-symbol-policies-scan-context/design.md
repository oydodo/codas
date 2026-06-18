# Design — P3 A2: migrate symbol policies to ScanContext

Authority: `docs/codas-implementation-plan.html` §11 (Adapter Boundary), §6
(Facts). Builds on A1 (`codas.facts.context.ScanContext`).

## `ScanContext.symbols()`

Add a memoized accessor mirroring `doc_claims()`:

```python
from codas.adapters.python import SymbolFact, SymbolFacts, extract_symbol_facts
...
    def symbols(self) -> SymbolFacts:
        if "symbols" not in self._cache:
            self._cache["symbols"] = extract_symbol_facts(self.repo, self.files)
        return self._cache["symbols"]
```

`extract_symbol_facts` already returns an immutable, fully-sorted `SymbolFacts`
(`adapters/python.py:47-48`), so no wrapping/sorting is added — the accessor caches
the object and returns it identically each call (determinism). Emits **all**
definitions; filtering stays in the policies because the two filter differently
(duplicate_symbol drops `_`-prefixed names, duplicate_implementation keeps them).

## Fact-type surfacing (the one real decision)

Both policies annotate `dict[str, list[SymbolFact]]`, so the `SymbolFact` *type*
must be importable without importing the adapter. Options:

- **(A) Re-export from the facts seam (chosen).** `context.py` already imports
  `SymbolFact`/`SymbolFacts` for the accessor signature; surface them via an
  explicit `__all__` so policies do `from codas.facts.context import ScanContext,
  SymbolFact`. The policy then depends on `codas.facts` (the normalization layer,
  allowed to import adapters), never on `codas.adapters`. Minimal, satisfies the
  boundary, and the B2 import-guard (which bans `codas.policies.* → codas.adapters`)
  stays green.
- (B) Relocate `DocClaim`/`SymbolFact` into a neutral `codas.facts.types` module
  that the adapter imports and populates. Cleaner long-term dependency graph
  (adapter→facts←policies, facts as shared vocabulary) but touches
  `adapters/{python,markdown}.py` + inventory; deferred to a follow-up cleanup
  (recorded as a P3-later non-goal).

Decision: (A) for A2 scope discipline; flag (B) for codex sign-off.

## Policy migrations

`duplicate_symbol.py`:
- imports → drop `from codas.adapters.python import SymbolFact, extract_symbol_facts`
  and `from codas.structure.index import discover_files, workspace_roots`; add
  `from codas.facts.context import ScanContext, SymbolFact`.
- signature → `def check_duplicate_symbol(ctx: ScanContext) -> list[Finding]`.
- body → delete the 3 scan lines (`:26-28`), `facts = ctx.symbols()`. Filter/sort
  unchanged.

`duplicate_implementation.py`:
- imports → drop the adapter + index imports; keep
  `from codas.config.loader import ConfigLoadError, load_claims` (claim loading
  stays in the policy); add `from codas.facts.context import ScanContext, SymbolFact`.
- signature → `def check_duplicate_implementation(ctx: ScanContext) -> list[Finding]`.
- body → `claims_path = ctx.repo / ".codas" / "claims.yml"`; delete the 3 scan
  lines (`:46-48`), `facts = ctx.symbols()`. Claim validation + module-set-aware
  suppression + finding construction unchanged.

`check.py`:
- `findings.extend(check_duplicate_symbol(ctx))`
- `findings.extend(check_duplicate_implementation(ctx))`

## Tests

- Migrate call sites in `tests/test_duplicate_symbol_policy.py` (10) and
  `tests/test_duplicate_implementation_policy.py` (9): add a `_ctx(repo) ->
  ScanContext` helper (`build_scan_context(repo, _config(repo))`) and replace
  `check_*(repo, _config(repo))` → `check_*(_ctx(repo))`. The claim-schema tests in
  test_duplicate_implementation_policy.py still write `.codas/claims.yml` into the
  temp repo; `ctx.repo` resolves it exactly as `repo` did.
- New `ScanContext.symbols()` test in `tests/test_scan_context.py`: returns a
  `SymbolFacts`, cached (identity-stable), matches `extract_symbol_facts`.
- **Generalize the import guard.** Replace the stale-claim-scoped guard with
  `test_no_policy_imports_adapter`: iterate every `src/codas/policies/*.py`, AST-parse
  (with the A1 relative-import resolver), assert none import a `codas.adapters.*`
  module. (Drop the `codas.structure.index` clause from the general guard — other
  policies legitimately use `codas.structure.index`; only an *adapter* import is the
  boundary violation. Keep a focused stale_claim assertion if useful.) This is the
  interim guard; B2 turns it into a dogfooded Codas finding over import facts.

## Verification

1. `PYTHONPATH=src python3 -m codas check .` → "No Codas findings" (the 4 declared
   `variant` claims in `.codas/claims.yml` still suppress the private-helper dups).
2. `codas inventory . --json` twice → byte-identical (unchanged — no structure/unit
   change this slice; symbols block already present).
3. `PYTHONPATH=src python3 -m unittest discover -s tests` → green.
4. `grep -rl "codas.adapters" src/codas/policies/` → empty.

## Dogfooding

No new module or governance file → no `structure.yml`/`config.yml`/`documents.yml`
change. (`codas.facts` already registered in A1.)

## Open questions for codex design review

- (A) re-export vs (B) relocate fact types — confirm (A) is acceptable for A2 and
  (B) is a legitimate separate cleanup, not a boundary half-measure.
- Generalized guard banning only `codas.adapters` (not `codas.structure.index`) —
  correct reading of the §11 boundary for the policy layer?
- Any determinism risk from caching the same `SymbolFacts` object across the two
  policies that both read it (they only read; no mutation)?
