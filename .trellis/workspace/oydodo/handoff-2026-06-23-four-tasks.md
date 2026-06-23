# Handoff — create 4 tasks (2026-06-23)

For the NEXT session. Goal: create 4 Trellis tasks from a long architecture dialogue.
**Full context + reasoning: `docs/codas-architecture-decisions.md`** (committed `c656b0b`).
Reviewable visuals: `codas-architecture.html` + `codas-concept-map.html` (repo root, committed).

## State at handoff
- Codex agent integration: SHIPPED + merged + archived.
- Swift extraction task: ARCHIVED (design-only; tree-sitter impl superseded — its design is reusable for task ③, in `.trellis/tasks/archive/2026-06/06-22-swift-extraction/design.md`).
- Decision record + 2 HTML concept maps: committed (`c656b0b`).
- No active Trellis task. main is clean.
- **Priority NOT yet locked** — user accepted all 4 tasks but did not pick the first. Confirm order with user (my recommendation: ① first). Don't assume.

## The 4 tasks to create

Each → Trellis create→start→archive, own worktree (`../harness-<slug>` + `feat/<slug>`).
gate-semantics tasks → **codex DESIGN review BEFORE impl** (iron rule).
NOTE: codex MCP has stalled repeatedly this project — if codex-rescue returns interim
"still reading", SendMessage it; if it stalls twice, fall back to a Claude-native
general-purpose adversarial reviewer (worked well this session).

### ① drop-hash + unified diff verification  [gate-semantics] [recommended FIRST]
- **What**: retire the whole-inventory `source_inventory_hash` freshness mechanism; verify ALL committed derived artifacts by re-render + byte-compare (diff), like the book + AGENTS.md already do.
- **Why**: the hash is an INPUT fingerprint (only facts) → misses prose + renderer changes; diff compares actual OUTPUT → catches everything. Also kills churn (whole hash re-stamps unrelated artifacts on any change) + removes the scoped/whole/diff inconsistency.
- **Scope**: convert `generated_wiki_drift` from hash-pin → re-render+byte-compare; stop embedding `source_inventory_hash` in `render_generated_overview` (wiki.py); keep determinism as the run-twice TEST (canonical serialization stays); keep `inventory_hash` (provenance.py) ONLY as an optional audit/receipt fingerprint (not for freshness).
- **Decision points for user**: (a) keep `inventory_hash` for audit or drop? (lean keep) (b) generated-page byte-compare per-commit (gated, current) vs CI-only? (lean keep gated, it's small).
- **Effort**: ~1-2 days. Key files: `core/provenance.py`, `app/wiki.py` (~470 narrowed-hash + 172/376 pack whole-hash), `policies/generated_wiki_drift.py`, `app/book.py:295` (the diff precedent to copy).
- **Why first**: most certain (designed in detail), de-risks, prerequisite for the multi-lang book render (②), removes the hash tax.

### ④ Problem-3 anchors + RepairTarget  [gate-semantics] [highest product value]
- **What**: catch "decision changed the code but the PRD/design doc wasn't updated" at commit, and hand the agent the exact fix.
- **3 pieces**: (1) let decision/design docs carry `defines:/calls:/contains:` anchors (today only `.codas/wiki/code/**` can — extend the anchor-bearing root via a config knob); (2) DERIVE the co-change gate from the anchor (anchor = coupling declaration — stop hand-writing claims.yml entries); (3) **RepairTarget**: when an anchor breaks, emit the stale span + old node + best-match new node (from the fact-delta, e.g. a rename) + the action, injected to the agent.
- **Tier invariant (must hold)**: detection (code_anchor) = advisory/warning, works on all langs; the co-change GATE resolves ONLY against in-core deterministic facts (Python ast). A gate-claim may never key on an open-world/external fact.
- **Scope boundary**: anchor-bearing = LIVE decision/design docs, NOT archived PRDs (archived PRDs describe past state → would false-drift against current code).
- **Existing seed (reuse)**: claims.yml already has ONE hand-written instance — "public symbol in `openworld.py` changes → `docs/codas-design.html` must co-change". Task ④ generalizes this (anchor-derived, multi-doc) + adds RepairTarget.
- **Novel parts (need design + codex review)**: deriving coupling FROM anchors; computing the rename best-match for RepairTarget.
- **Effort**: ~3-5 days. Key files: `policies/code_anchor.py` (anchor scope), `policies/fact_coupling.py` (the co-change gate + claims.yml load), `app/preflight.py` / injection (RepairTarget delivery).
- Also folds the "claim overload" cleanup: claims.yml `fact_coupling` and doc anchors are the same thing two ways → converge on the anchor.

### ② CodeGraph advisory call-graph adapter  [low risk, off-gate]
- **What**: CodeGraph (colbymchenry/codegraph — Node, tree-sitter-based, MIT, no LLM, multi-lang, SQLite) as the **multi-language + cross-language call-graph adapter**, feeding the ADVISORY tier only.
- **Scope**: `adapters/codegraph.py` — subprocess to the CodeGraph CLI, map its graph → `SymbolFact`/`ImportFact`/`CallFact` with `provenance=codegraph` + resolution tags; new `ScanContext` accessors (`codegraph_*()`) that NEVER enter the inventory hash or any gating policy; graceful-degrade to empty when the binary is absent (open-world). Feed `codas impact` + preflight reuse hints. Cross-language/heuristic edges stay advisory (never gate — guessed edges would false-block).
- **Constraints**: optional dependency (pyproject stays pyyaml-only; CodeGraph is an external Node tool, not a pip dep); NOT in gate, NOT in hash.
- **Effort**: ~2-3 days + install CodeGraph in the dev env. Key file: `facts/context.py` (the additive accessor seam).
- **Note**: this is the migrate-LITE position (5 advisors converged). Do NOT make CodeGraph gate-grade / diff-model / retire inventory — those were rejected.

### ③ tree-sitter gate adapter (per-language symbols/imports)  [medium]
- **What**: for a language you want to GATE (e.g. Swift for the ciri repo), hand-build a deterministic in-core tree-sitter extractor for **symbols + imports** (the EASY layer-2 part; NOT the call-resolver). These feed the gate (ownership/duplicate/dependency-direction) per-language.
- **Why tree-sitter not CodeGraph here**: gate needs determinism; tree-sitter in-process is inherently deterministic (like ast). CodeGraph (non-det, external) stays advisory (②).
- **Scope**: optional extra `codas[swift]` (`tree-sitter~=0.23, tree-sitter-swift~=0.7`); `adapters/swift_parse.py` + `adapters/swift.py` (extract_swift_symbols/imports); `facts/languages.py` light registry; `ScanContext.symbols()/imports()` additive merge with **early-return on empty extra** (byte-identical for Python-only repos). Calls DEFERRED (advisory via CodeGraph). Fixtures via `tmp_path`, NEVER committed under a scanned root.
- **Existing design**: `.trellis/tasks/archive/2026-06/06-22-swift-extraction/design.md` (+ codex review folded) is directly reusable — Swift was the worked example.
- **Effort**: ~1-2 days per language. gate-semantics (touches fact extraction) → codex DESIGN review (most of it is in the archived design).

## Recommended sequence
A (foundation-first): ① → ④ → ② → ③. Rationale: ① is most certain + de-risks + prereq for the multi-lang book; ④ is the product payoff; ②/③ are multi-language reach (do when actually onboarding ciri). User may prefer B (④ first, product) or C (② first, multi-lang/ciri) — CONFIRM.

## Process reminders (this repo's iron rules)
- EVERY task → Trellis create→start→archive. No low-risk exemption. Don't hand-edit task.json.
- gate-semantics (①③④ touch fact-extraction/gate) → codex DESIGN review BEFORE impl.
- Worktree per task; main can have concurrent sibling worktrees (don't trample).
- `hooks --install` default `--command` assumes `codas` on PATH; on this source checkout pass `--command "PYTHONPATH=src python3 -m codas check ."` or you regress the SHARED `.git/hooks/pre-commit`.
- Run gate with `PYTHONPATH=src python3 -m codas check .`; tests `python3 -m unittest discover -s tests` (no pytest in env).
