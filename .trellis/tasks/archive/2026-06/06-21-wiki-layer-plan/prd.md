# Wiki-layer detailed design + artifact taxonomy + post-P7 roadmap (PLANNING)

## Status
PLANNING. The deliberate ANTIDOTE to reactive building. Output = a DESIGN/decision record +
a roadmap landed in program.yml / CONTEXT.md — NOT code. No implementation in this task.

## Why (the trigger — user, 2026-06-21)
Since P7 the work went "想到什么做什么" (reactive): Block A knowledge tree, W3 S1 views, W3 S3
calibrator, prove-end-to-end, judge-delegation, persistent semantic wiki — each individually
sound (full Trellis + codex review) but with NO unified wiki-layer design and NO post-P7
roadmap. Fragments are stacking without an overall picture. This is exactly the unplanned
sprawl Codas itself exists to govern (the dogfood irony). Stop and plan before building more.

## Questions this planning task must answer
1. **What IS the wiki layer, end to end?** A single coherent system, or a loose pile? Draw the
   one picture: inputs (facts) → artifacts → consumers (host agent / human / CI).
2. **Artifact taxonomy + FORMS.** Enumerate every wiki artifact already built + planned, and pin
   for each: form (JSON / .md / HTML / mermaid / feed / tags), committed vs ephemeral, in-hash
   vs out-of-hash, who produces it, who consumes it, its lifecycle, its verifier (if any):
   - knowledge_tree/v1 (Block A, `--emit-tree`)
   - atlas pack (`--emit-pack`)
   - semantic FEED + calibration (W3 S3, `--emit-feed`/`--calibrate`)
   - mermaid + html views (W3 S1)
   - generated governance page (`.codas/wiki/generated/`, D3b)
   - code-wiki (W1, `.codas/wiki/code/` + code_anchor)
   - persistent semantic wiki (`.codas/wiki/semantic/` + check_semantic_wiki)
   - concepts (`.codas/wiki/concepts/`) + index.md
   - the (deliberately ephemeral) `.codas/cache/semantic/` corpus
3. **Coherence pass.** Do these fit a clean model (e.g. the 3-layer raw/wiki/schema from the
   Karpathy-framework positioning, or the FEED/VERIFY/VIEW split)? Where do they overlap,
   duplicate, or conflict (e.g. code-wiki vs semantic-wiki; ephemeral vs persistent corpus)?
   What should be UNIFIED, RENAMED, or RETIRED?
4. **The "wiki库" decision.** Is there a single browsable persistent knowledge store, and what
   is its canonical form? How do committed pages, generated pages, and views relate?
5. **Post-P7 ROADMAP.** Define phases/priorities/acceptance for what remains. Place the deferred
   items: S2 multi-lang, Block B (CodeWiki), `--scope`, code_anchor↔semantic_wiki unification,
   W3 judge productization, adoption/packaging. What is next, what is opt-in, what may never ship.
6. **Land it.** Update `.codas/program.yml` (the phase/roadmap source of truth) + the relevant
   CONTEXT.md / docs section so the plan is durable + dogfood-checkable, not just prose.

## Method (to decide with the user)
This is strategic + the user's domain → run it as a structured DESIGN exploration, not a solo
draft. Candidates: grill-me (user drives, one question at a time), a brainstorm workflow
(multi-lens: taxonomy / coherence-model / roadmap + adversarial critique), or a hybrid.

## Acceptance
- [ ] A wiki-layer design/decision record: the one picture + the artifact taxonomy table +
      the coherence verdict (unify/rename/retire) + the wiki库 decision.
- [ ] A post-P7 roadmap landed in program.yml (+ CONTEXT.md/docs pointer), with deferred items placed.
- [ ] No code. (Any build that the plan calls for goes through its own later Trellis task.)
