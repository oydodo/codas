# Block A — neutral Codas knowledge-tree emitter (the deterministic organization layer)

## Status
IMPLEMENTED (2026-06-20). `codas wiki --emit-tree` ships the deterministic ORGANIZATION
layer: `project_atlas_tree` / `build_atlas_tree` in src/codas/app/wiki.py, tests in
tests/test_knowledge_tree.py. 432 tests green, `codas check .` 0, inventory + emit-tree
byte-identical, wiki --verify clean. Built after a codex DESIGN review (4 BLOCKERs, all
resolved) AND a codex IMPL review (0 BLOCKERs; 3 SHOULD-FIX + 1 NIT folded — ownership
tie-break documented, edge-dedup commented, +2 tests: constructor-no-relabel & empty
inventory). Scope stayed NARROW: only the organization layer; semantic-synthesis +
provenance + judge deferred to W3 (their consumer). See memory [[codas-wiki-architecture]].

## What the wiki layer is FOR (the reframe that answers codex BLOCKER #2)
codex #2 said the calibrated corpus adds no new TRUSTWORTHY INFORMATION beyond the facts Codas
already has (CONFIRMED = restated facts; SEMANTIC = unverified) -> "no value". That measured the
wrong axis. The wiki's value is NOT another fact layer — it is the ORGANIZATION of scattered
facts (646 symbols + 775 call edges + imports + ownership) into a repo KNOWLEDGE SYSTEM that
enables HIGHER-COMPLEXITY cognition (the user's point). The wiki is the textbook to the facts'
dictionary: it adds no new words, but enables understanding the flat facts cannot.

That organization has TWO layers:
- **DETERMINISTIC ORGANIZATION** (Codas-built): scattered facts -> a hierarchical, navigable
  structure (module tree, call graph, ownership). Fact-derived + deterministic -> a TRUSTWORTHY
  skeleton. **THIS is Block A.**
- **SEMANTIC SYNTHESIS** (LLM-produced, later): narrative over the structure making higher-order
  concepts explicit ("the auth subsystem", "this layer's responsibility") — the higher-cognition
  the user wants. UNTRUSTED, but ANCHORED to the deterministic structure. **This is W3.**

The judge (W3) reasons at high complexity over the SYNTHESIS, but grounds every conclusion in
the ORGANIZATION/facts. So the "calibrator" is reframed = PROVENANCE-ANCHORING (snap a synthesis
claim back to the deterministic structure/facts so the judge can ground it), NOT a trust-stamp
(codex #2's own fix). For Block A (pure projection, no LLM) the circularity is DISSOLVED — a
hierarchy over positive facts adds no synthesis authority. For W3 it is CONTAINED, not eliminated
(codex re-review): facts stay the SOLE authority and the judge must ABSTAIN — never upgrade a
SEMANTIC or UNCONFIRMED claim to trusted (absence is UNKNOWN, not denial, per the open-world
invariant). The synthesis is high-quality hypotheses the judge verifies, never trusts.

## Codex review status (2026-06-20)
codex design review round 1: 4 BLOCKERs. Round 2 (re-review of this revision): all 4 RESOLVED,
the user's organization-value rebuttal judged SOUND, Block A's standalone value CONFIRMED (a
navigable tree with parent/children + ownership + resolution-tagged call adjacency is materially
more than the flat inventory). Remaining items, all FOLDED into this design: call edges carry
`resolution` (objects, not bare ids); method nodes defined as call-endpoint-derived lower-bound
nodes; `owner` -> `unit_id`+`unit_owner`; CLI = `codas wiki --emit-tree`; "dissolves" -> "contains"
for W3. Design is implementation-ready (no code written yet, per user directive).

## Scope (Block A — ONE piece, license-clean, tool-agnostic)
**A neutral Codas knowledge-tree EMITTER.** Project the verified symbol/call/import/ownership
facts into a hierarchical, navigable KNOWLEDGE TREE, in a NEUTRAL, versioned Codas schema
(NOT CodeWiki's private first_module_tree.json — codex #6: the license-clean core must not be
coupled to an unlicensed tool's undocumented format). Deterministic, pure projection, no LLM,
NOT in the inventory hash. Independent value, today:
- the injection SPINE any generator narrates over (host-agent-direct primary; CodeWiki via a
  Block-B adapter that maps neutral -> CodeWiki schema);
- a better PREFLIGHT context than flat facts (organized > scattered);
- the substrate the W3 synthesis layer is built on.

## Out of scope (DEFERRED to W3 — codex #3, premature-build)
- The semantic-SYNTHESIS layer (LLM narrative) — needs the judge to consume it.
- The PROVENANCE-anchoring "calibrator" — an OFFLINE tag artifact for W3 fixture authoring, NOT
  a `codas check` warning (UNCONFIRMED-as-warning would be noisy on open-world lower-bound facts).
- The unified corpus-claim reader that subsumes W1's `anchor_symbol` as `defines` (codex #4) —
  built with the synthesis layer, not now.
- The W3 judge itself. Block A is its substrate.
- Block B (the FSoft CodeWiki shell-out adapter, license-gated).
- Writing code this round.

## Acceptance (MET)
- [x] The emitter output is a NEUTRAL Codas schema (`codas.knowledge_tree/v1`, versioned),
      deterministic + byte-stable (run-twice byte-identical, the house pattern), NOT CodeWiki's schema.
- [x] Component identity is class/resolution-precise (codex #1) — node-id `<path>::<class>::<symbol>`,
      no same-name collision; call edges carry `resolution`.
- [x] Scope + module-name convention DEFINED + implemented (codex #5): reused the existing
      `_in_product` helper (no clone); repo-rel path spine; product root `src/codas`.
- [x] §11/§17 clean; pure inventory-dict projection; printed to stdout (not in the inventory
      hash); no LLM, no ScanContext re-scan.
