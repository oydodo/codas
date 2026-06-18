# Design — P3 A1: fact-provider / scan-context

Authority: `docs/codas-implementation-plan.html` §11 (Adapter Boundary), §3
(System Layers), §5 (modules), §6 (Fact/Claim/Finding); `.codas/program.yml`
`program:P3:adapter-extraction`.

## Boundary rule (verbatim)

§11: *"Boundary rule: if a concept only makes sense in one ecosystem, it belongs
in an adapter. Core may only receive normalized facts and claims."* §3: *"Core
domain must not import Swift, Trellis, GitHub, Codex, Claude Code or any
product-specific integration."*

`policies/` is core (the policy engine: facts → claims → policies → findings). A
policy importing `codas.adapters.markdown` / `codas.adapters.python` reaches into
ecosystem-specific extractors (Markdown link parsing, Python AST) — a
dependency-direction violation. The coupling is shallow: each policy consumes only
the already-normalized frozen dataclass (`DocClaim` / `SymbolFact`), so removing
the import is a pure direction fix, not a data-shape change.

## Decision: new `ScanContext`, do not reuse `build_inventory`

`build_inventory(repo) -> dict[str, Any]` (`structure/inventory.py:21`) is the
inventory artifact renderer: it returns a flat JSON-serialization dict (not typed
objects), hardcodes loaders a policy does not need (structure_map, program_plan,
document_manifest), and is the thing whose output must stay byte-identical.
Threading it into policies would force lossy dict→dataclass round-trips and risk
the inventory JSON. So A1 leaves `build_inventory` **untouched** and adds a
sibling provider.

## Module: `src/codas/facts/context.py` (new `codas.facts` package)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from codas.adapters.markdown import DocClaim, extract_doc_claims
from codas.config.loader import CodasConfig
from codas.structure.index import discover_files, workspace_roots


@dataclass(frozen=True)
class ScanContext:
    repo: Path
    config: CodasConfig
    roots: tuple[str, ...]
    files: tuple[str, ...]
    _cache: dict = field(default_factory=dict, init=False, compare=False, repr=False)

    def doc_claims(self) -> tuple[DocClaim, ...]:
        if "doc_claims" not in self._cache:
            self._cache["doc_claims"] = tuple(extract_doc_claims(self.repo, self.files))
        return self._cache["doc_claims"]


def build_scan_context(repo: Path, config: CodasConfig) -> ScanContext:
    roots = workspace_roots(config.raw)
    files = tuple(discover_files(repo, roots))
    return ScanContext(repo=repo, config=config, roots=roots, files=files)
```

- **The provider seam (narrow exception, not broadened core permission).** §11
  says *core receives normalized facts* — it does not say core imports adapters.
  `codas.facts` is the normalization layer that sits *between* adapters and core
  (the §5 fact layer), exactly where an adapter import is legitimate; it is not
  "core". `context.py` is the single point where adapter output crosses into
  normalized facts, and the B2 import-guard whitelists `codas.facts.context`
  specifically — it does not relax the ban for `codas.policies.*` or the rest of
  core. Naming it a "provider seam" not a "core module with extra rights" is the
  intended reading.
- **Caching on a frozen dataclass.** `_cache` is a plain dict field. `frozen=True`
  blocks attribute *reassignment* (`self.x = ...`) but `self._cache[k] = v`
  mutates the dict in place and is allowed. `compare=False, repr=False` keep the
  dataclass equality/repr clean. Each accessor returns the identical, already
  adapter-sorted tuple every call — determinism preserved.
- **`files` cached once.** `discover_files` runs exactly once at build time;
  `roots` from the single `workspace_roots` source so the default-roots rule
  cannot fork across policies. Retires the per-policy re-scan debt for the
  migrated policy (fully retired in A2 when the symbol consumers move).

## `check.py` threading

After `config = load_codas_config(config_path)` succeeds, build one context:

```python
from codas.facts.context import build_scan_context
...
ctx = build_scan_context(repo, config)
...
findings.extend(check_stale_claim(ctx))   # was check_stale_claim(repo, config)
```

The other 11 `check_*(repo, config)` calls are unchanged in A1. `ctx.repo` /
`ctx.config` remain reachable, so no information is lost when more policies migrate.

## `stale_claim` migration

New signature `check_stale_claim(ctx: ScanContext) -> list[Finding]`. Delete the
imports at `stale_claim.py:5` (`extract_doc_claims`) and `:8`
(`discover_files, workspace_roots`); delete the two scan lines (`:20-21`); replace
`claims = extract_doc_claims(repo, tuple(files))` with `claims = ctx.doc_claims()`.
Finding construction + the total-order re-sort (`:24-44`) are unchanged. The policy
keeps only `from codas.core.models import Evidence, Finding` plus the new
`from codas.facts.context import ScanContext` (a core/facts import, not an
adapter/ecosystem one — boundary clean).

## Tests

- **Migrate call sites** (option A — single canonical signature). In
  `tests/test_stale_claim_policy.py`, wrap each `check_stale_claim(repo, cfg)` as
  `check_stale_claim(build_scan_context(repo, cfg))`. Rejected option B (2-arg
  back-compat shim) re-introduces per-call scanning and defeats the dedup goal.
- **New** `tests/test_scan_context.py`: `build_scan_context` populates `files`
  (non-empty, sorted, repo-relative); `doc_claims()` returns a tuple, is cached
  (same object identity on second call), and matches `extract_doc_claims` output;
  `roots` defaults to `(".",)`.
- **Regression guard** `tests/test_scan_context.py::test_stale_claim_imports_no_adapter`:
  `ast.parse` the `codas.policies.stale_claim` module file and walk
  `Import`/`ImportFrom` nodes, asserting no imported module starts with
  `codas.adapters` or equals `codas.structure.index`. AST (not substring) so a
  comment or string mentioning the module never false-trips. Scoped to the
  migrated file; the general policy-layer ban is B2.
- `tests/test_codas_check.py` dogfood assertions unchanged (still `assertNotIn
  "stale-claim"`); run_check now threads ctx internally.

## Verification

1. `PYTHONPATH=src python3 -m codas check .` → "No Codas findings".
2. `codas inventory . --json` twice → byte-identical and unchanged from baseline.
3. `PYTHONPATH=src python3 -m unittest discover -s tests` → green.
4. `grep -rn "codas.adapters" src/codas/policies/stale_claim.py` → empty.

## Dogfooding registration

`src/codas/facts/` is a new module → register a Structure Map unit in
`.codas/structure.yml` (e.g. `codas-facts`, path `src/codas/facts`, status active,
owner Core Maintainer) and add it to the `codas-source` `allowed_children` so
`missing_structure_owner` / `structure_drift` stay quiet. No new governance file,
so no `config.yml` / `documents.yml` change. (Confirm the existing `codas-source`
unit's prefix already covers `src/codas/facts` — if a catch-all already owns it,
add the explicit unit anyway for an addressable owner and to mirror how
`adapters` / `policies` / `structure` are each declared.)

## Open questions for codex design review

- Provider home `codas.facts` vs `codas.structure.scan` — facts package names the
  §5 normalization seam; confirm.
- `_cache` dict on a frozen dataclass vs non-frozen + `functools.cached_property` —
  is the in-place-dict-mutation idiom acceptable, or prefer cached_property with a
  non-frozen class? (Determinism holds either way.)
- Interim per-file import guard (A1) vs waiting for the B2 policy — acceptable as a
  scoped regression test?
- Confirm `build_inventory` staying untouched is the right call to protect the
  byte-identical inventory invariant (vs unifying the scan now).
