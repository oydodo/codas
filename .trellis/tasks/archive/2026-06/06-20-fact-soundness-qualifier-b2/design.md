# B2 design — fact soundness qualifier (implementation spec)

## New module: src/codas/facts/soundness.py
- THREE primitive levels, a TOTAL order for composition (strength desc):
  `EXACT` > `SCOPED` > `APPROXIMATE_INCOMPLETE`. Represent as an IntEnum or module
  constants with an explicit numeric rank (EXACT=2, SCOPED=1, APPROXIMATE_INCOMPLETE=0)
  so `meet` = min. ("derived" from the model is NOT a primitive level — it is what `meet`
  produces; document that.)
  - EXACT: complete + precise for what it claims.
  - SCOPED: complete WITHIN a declared scope (bound stated in `scope`), nothing missing
    inside it.
  - APPROXIMATE_INCOMPLETE: known to under-approximate (named in `under_approximates`).
- `@dataclass(frozen=True) FactFamilySoundness{family:str, level:int, scope:str,
   under_approximates:tuple[str,...]}` with a `as_dict()` -> sorted-keys dict
   {family, level (the LOWERCASE name string, e.g. "approximate_incomplete"), scope,
   under_approximates (list)}.
- `meet(a:int, b:int)->int` = min; `meet_all(levels)->int` = min, EXACT on empty.
  Pure. Document: the first multi-family CLAIM consumer is B4; meet is the family algebra.
- `FACT_SOUNDNESS: dict[str, FactFamilySoundness]` — the manifest, frozen content:
  - "symbols": level SCOPED, scope "top-level Python definitions (class/function) resolved
     by stdlib ast", under_approximates ("methods","nested definitions",
     "conditionally-defined or dynamically-created symbols").
  - "imports": level APPROXIMATE_INCOMPLETE, scope "static Python import statements,
     first-party targets resolved by stdlib ast", under_approximates ("dynamic imports
     (importlib / __import__)","conditional or function-local imports not reached",
     "re-exports").
  - "calls": level APPROXIMATE_INCOMPLETE, scope "first-party static-resolved call edges
     (stdlib ast, no third-party analyzer)", under_approximates ("dynamic dispatch /
     calls through variables or returns","super() / MRO / cross-class instance dispatch",
     "reflection (getattr / dynamic)","builtins and external (non-first-party) calls").
- `LEVEL_NAMES`: rank->name + name->rank helpers so serialization is the lowercase name
  (stable), never the int, in inventory/impact output (determinism + human-legible).
- `family_soundness(family:str)->FactFamilySoundness | None`.

## Inventory surfacing: src/codas/structure/inventory.py
- Add a top-level `fact_soundness` block = `{family: family.as_dict()}` for the 3 families,
  built from FACT_SOUNDNESS, sorted by family key (json sort_keys already sorts; build a
  plain dict). It is a STATIC constant -> byte-identical. Place it near the symbols/imports/
  calls blocks. Do NOT touch the existing blocks' shape (no per-row field) -> existing
  symbol/import/call rows stay byte-identical; only a new sibling block is added.

## Consumer with teeth: src/codas/app/impact.py
- `compute_impact(...)` result dict gains `"soundness": family_soundness("calls").as_dict()`
  -> the agent sees the impact (reverse-reachability over calls) is a LOWER BOUND.
- `render_impact_text(...)` prints a one-line caveat after the header when affected/matched
  exist, e.g.: `note: calls are approximate_incomplete — misses dynamic dispatch, super/MRO,
  reflection; the affected set is a lower bound.` (render the under_approximates joined).
- Determinism preserved (constant); add a test that impact --json carries soundness and is
  byte-identical.

## §11 / §17 / determinism
- soundness.py is pure stdlib, a constant manifest — no LLM, no nondeterminism. It lives in
  `codas.facts` (the seam package) — it does NOT import an adapter, so any layer may import
  it. impact.py already imports from codas.facts (CallFacts via facts.context); importing
  facts.soundness is the same allowed direction.
- NAME-COLLISION guard: grep `^def meet`, `^def family_soundness`, `^def meet_all`,
  `^class FactFamilySoundness` across src to avoid the duplicate_implementation trap; the
  names above are believed unique — verify before finishing.
- Orchestration: no new ctx-consuming policy, so test_codas_check monkeypatch is UNCHANGED.

## Tests: tests/test_fact_soundness.py
- meet/meet_all (min, empty=EXACT, order).
- FACT_SOUNDNESS has the 3 families; levels as specified; as_dict() shape + lowercase name.
- inventory has fact_soundness block, 3 families, byte-identical across 2 runs (assert the
  whole inventory json is identical 2x).
- impact result carries calls soundness; render_impact_text shows the caveat when there is
  an affected set and omits/!crash on the miss case.
- determinism: impact --json byte-identical 2x.

## Verify (the implementer MUST run, capture pass/fail honestly)
PYTHONPATH=src python3 -m unittest discover -s tests   # all green
PYTHONPATH=src python3 -m codas check .                # No Codas findings
PYTHONPATH=src python3 -m codas inventory . --json | shasum  # 2x identical
PYTHONPATH=src python3 -m codas wiki --verify .         # up to date
