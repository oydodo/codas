# PRD — call-graph facts (pyan adapter, optional extra)

## Context

A dogfood spike + an OSS survey (this session) found Codas's real gap: it has
module-level **import** facts + top-level **symbol** facts, but **no call graph**
(no caller/callee edges). That gap makes the planned `spec_drift` policy's
`must_update_if_changed` enforcement uselessly coarse ("any change under src/ must
update docs"). A call graph gives precise change-impact ("you changed
`build_scan_context`; its real callers are `run_check` + these tests"), and also
upgrades `preflight` (blast radius) and unlocks call-level policies (dead code,
test-coverage, finer boundary checks).

Build-vs-borrow was settled (research a74427a3 + a live test): **borrow pyan3**
(Technologicat/pyan, GPL-2.0, accepted by the user). It does proper ast+symtable
lexical-scope resolution (super/MRO/inheritance) — far better than the lossy
alternatives — and a live probe on Codas extracted the correct graph
(`run_check -> all 15 check_* policies`, 2529 edges). pyan is **Python-only**, which
is fine: it is a per-§11 adapter; the emitted call facts are language-neutral so
future per-language adapters feed the same block.

**Decision: optional extra (the user chose B over a hard dependency).** Codas's core
stays `pyyaml`-only / stdlib / run-anywhere. pyan + the `calls` facts ship as
`pip install codas[callgraph]`. When pyan is absent, the `calls` facts are simply
unavailable (graceful), and `spec_drift` (later) falls back to coarse mode. This
keeps Codas lean and confines the GPL dependency to opt-in installs.

## Requirements

1. New adapter `src/codas/adapters/callgraph.py` (isolates the optional pyan import):
   - `extract_call_facts(repo, files) -> CallFacts`. **Lazy** `import pyan` inside the
     function; on `ImportError` return `CallFacts(edges=(), available=False,
     skipped=("pyan-not-installed",))` — never import pyan at module top.
   - With pyan present: run `CallGraphVisitor` over the repo's `.py` files (pass an
     explicit `root` for stable module names), read `uses_edges`, keep an edge only
     when **both** endpoints are first-party (`defined == True`, dropping
     `Flavor.UNKNOWN`/builtin/unresolved `*.x` nodes), normalize to `CallFact`,
     dedup, stable-sort.
   - `CallFact`: caller (module, symbol, path, line) + callee (module, symbol, path,
     line). `CallFacts`: `edges`, `available: bool`, `skipped`.
2. Inventory `structure/inventory.py`: emit a `calls` block
   (`{available, sources, edges, skipped}`), mirroring `imports`. Always present
   (carries `available=false` when pyan absent) for schema stability.
3. Seam `facts/context.py`: memoized `calls()` accessor + re-export
   `CallFact`/`CallFacts`.
4. `pyproject.toml`: add `[project.optional-dependencies] callgraph = ["pyan3>=2.6"]`.
   Core `dependencies` stays `["pyyaml>=6.0"]`.
5. Dev environment: a 3.11+ venv with `pyyaml` + `pyan3` becomes the dogfood gate
   (the existing `python3` on this box is 3.9, below pyan's >=3.10 / Codas's existing
   pyproject >=3.11). Document it in AGENTS.md / README so the gate is reproducible.

## Acceptance criteria

- With pyan installed: `extract_call_facts` on a fixture yields the expected
  first-party caller->callee edges with correct paths/lines; unresolved/builtin
  targets are dropped; deterministic across two runs.
- pyan absent (simulated ImportError): returns `available=False`, empty edges, no
  exception; `codas inventory`/`check` still run.
- `codas inventory . --json` (in the pyan venv) includes a populated `calls` block,
  byte-identical across two runs; `unowned` unchanged.
- `codas check .` → "No Codas findings" (facts-only, no policy added); full suite
  green in the 3.11+ pyan venv.

## Non-goals

- The `spec_drift` policy and any call-graph-consuming policy (dead-code,
  test-coverage) — separate slices; this ships the facts only.
- Cross-module call resolution beyond what pyan gives; multi-language call graphs
  (future per-language adapters).
- Making `calls` a hard dependency or wiring pyan into the core import graph (option
  A was rejected) — pyan stays opt-in and lazily imported.
- `defines` / `recursion` edge types from pyan (start with `uses` = calls; others
  later if needed).
