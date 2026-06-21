# Design — Wiki-layer plan (brainstorm + grill-me decisions)

Output of a 6-agent brainstorm (taxonomy / readable-system / coherence / roadmap → synthesis →
adversarial critique, workflow wlf4jvc99) + a grill-me with the user. This is a PLANNING record;
each build it calls for is its own later Trellis task.

## The problem
Since P7 the wiki work went reactive ("想到什么做什么"): Block A tree, W3 S1/S3, prove-end-to-end,
judge-delegation, persistent semantic wiki — each sound, but no unified design + no roadmap. The
fragments stacked. (Dogfood irony: unplanned sprawl is what Codas governs.)

## The decision: a TWO-PART split (user's load-bearing call)
The critic's sharpest point was that "a persistent readable wiki for BOTH humans and agents" is
inflated — agents already have the superior surface (`--emit-tree`/`--emit-feed`: structured JSON,
node-id-addressed, always fresh); a committed markdown book is strictly worse for an agent. The
USER resolved this by SPLITTING the audiences into two locations (and rejected "unproven demand":
the user is the reader — "我要看"):

- **`.codas/wiki/` = the MACHINE / SOURCE layer** (NOT for human browsing): the verified-claim
  surface for agents + `codas check`, plus the advisory "why" PROSE source. Stays as-is
  (governance page, the claim pages, concepts).
- **`wiki/` (repo root) = the HUMAN BOOK** (the persistent readable knowledge base the user reads).

This dissolves the dual-audience conflation: agents consume the FEED + `.codas/wiki/` claims;
humans read `wiki/`.

## The `wiki/` human book (the grill decisions)
- **Producer = `codas wiki --write` RENDERS it** (Q2): a deterministic SKELETON (nav/index +
  overview + per-subsystem chapters: a module→class→function tree-slice + a dependency mermaid +
  owner, all from facts/tree) WITH the advisory "why" PROSE WOVEN IN from `.codas/wiki/` source.
  Book = facts + why, one readable whole. `.codas/wiki/` = source; `wiki/` = rendered book.
- **Shape = a CHAPTER BOOK** (Q4): index/overview + one chapter per Structure-Map subsystem
  (~24 units). Read top-down like a technical book.
- **Prose fill = SKELETON-FIRST, prose incremental** (Q5): v1 renders all chapter SKELETONS
  (deterministic, immediately browsable structure); the "why" prose is a placeholder filled
  chapter-by-chapter over time by a host agent authoring into `.codas/wiki/` source + regenerate.
- **Determinism / hash**: `wiki/` is a DERIVED render → hash-EXCLUDED (add `wiki/` to the
  scan/exclude, like `.codas/wiki/generated/`), so the book never enters the byte-identical
  inventory hash. The render is a pure function of (facts + source prose), so `codas wiki
  --verify` can regenerate + byte-compare for freshness; it restales when facts move OR a source
  page changes (correct). The woven prose was authored non-deterministically (LLM) but, once
  committed in source, the render is deterministic. §17 holds: Codas renders with no model; the
  LLM only authors the advisory source prose (out of hash).
- Mermaid in the `.md` chapters renders on GitHub / any Mermaid viewer — the book is
  GitHub-browsable, NOT a self-contained offline HTML (that remains the ephemeral `--emit-html`).
- Every tree-derived chapter renders the open-world lower-bound caveat once, visibly (as
  `codas impact`/views already do) — a rendered "functions" list must not imply completeness.

## The canonical model (lands in program.yml / CONTEXT.md)
**Wiki artifacts classify by VERIFICATION CONTRACT, across two locations:**
1. **FEED** — ephemeral stdout, hash-excluded, pure inventory projection (`--emit-pack`/`-tree`/
   `-feed`/`--calibrate`/`--emit-mermaid`/`--emit-html`). Agent/CI/human-convenience. No verifier
   (inherits the inventory's).
2. **GENERATED (`.codas/wiki/generated/` + the new `wiki/` book)** — committed, deterministic,
   machine-rendered by `--write`, hash-EXCLUDED, freshness-verified by `--verify` (+
   generated_wiki_drift for the governance page's claims).
3. **WIKI-PAGES (`.codas/wiki/{code,semantic→unified,concepts}/`)** — committed advisory prose OUT
   of hash + a verified CLAIM block (warning, open-world). Two kinds: STRUCTURAL (code-graph
   claims defines/calls/contains) + REFERENCE (concepts/ + index.md: filesystem/config path +
   authority claims, IN-hash because the path-claims ARE the content).
4. **CACHE (`.codas/cache/semantic/`)** — gitignored AUTHOR scratchpad (the W3 offline corpus).

## UNIFY (internal cleanup — decided, minimal churn)
Merge `code_anchor` + `check_semantic_wiki` into ONE parser/policy/grammar (`anchor_symbol` is a
strict subset of `defines`; debt named at `.codas/policies.yml:56`). Keep the `code/` dir name,
retire only the "semantic" name; migrate `code/openworld.md`'s 3 `anchor_symbol` lines to
`defines:`. Gate with a golden PARITY test on the UNCHANGED pages BEFORE migrating. Do it while
`semantic/` is empty (cheapest now).

## Honest framing (critic, retained)
The `wiki/` book is a HUMAN artifact (agents use the FEED). Its value rests on the user reading it
(demand asserted by the user, not the market). The "one node-id address space" covers
structural+generated tiers, not the reference tier (concepts use filesystem paths) — two address
spaces, honestly. Determinism is preserved because the book is a hash-excluded derived render.

## Post-P7 ROADMAP (lands in program.yml)
- **W4 — render the `wiki/` chapter-book SKELETON** via `codas wiki --write` (deterministic:
  nav/index + overview + ~24 chapter skeletons + dependency mermaid + owner + open-world banner;
  `wiki/` hash-excluded; `--verify`-checked). The first build; the convergence that turns orphaned
  pages into a browsable book. (Today `.codas/wiki/index.md` dead-ends at 3 concepts.)
- **W5 — UNIFY** code_anchor + semantic_wiki (minimal churn + golden parity). Do while empty.
- **W6 — prose fill (incremental, ongoing)** — host agent authors per-chapter "why" into source.
- **W7 — CONTRACT.md wiki-layer doc**: the two-part split, the verification-contract model, the
  verifier-routing table (concept_page→stale_claim; canonical_source/evidence/sync_target→
  stale_wiki_claim; doc_claims) + the dual-hash explanation.
- **W8 — packaging** (pip/pipx + README quickstart; fix the README PYTHONPATH doc-lie). Parallel,
  pure moat-alignment, no wiki risk.
- **DEFERRED (placed, not roadmapped as commitments):** S2 multi-lang (moat-gated, may never ship);
  Block B FSoft CodeWiki (license-gated); `--scope` feed slicing (until measured friction); W3
  judge productization (after the book/loop has real use); `--promote` cache→committed (manual
  `git mv` until a real page demands a command).

## Acceptance (this planning task)
- [x] The two-part split + the verification-contract model + the `wiki/` book design are recorded.
- [x] The roadmap (W4–W8 + deferred placements) landed in `.codas/program.yml` (P8).
- [x] No code (each W-phase is its own later Trellis task; W4 is next).

## Codex PLAN review — corrections (2026-06-21, folded into the W4 design)
The plan's determinism mechanism for `wiki/` was WRONG; codex (af8b542) corrected it. W4 MUST
build to these, not to the original "hash-excluded like generated/" wording:
- **BLOCKER (the make-or-break): "hash-excluded like `.codas/wiki/generated/`" is a FALSE
  precedent.** generated/ is NOT removed from the default inventory hash — `exclude_under=
  _GENERATED_DIR` is passed only by the wiki builders (`build_atlas_pack`/`_generated_pages`),
  never by the default `codas inventory`/`check` scan, and `tests/test_atlas_pack.py:121`
  asserts excluding generated CHANGES the inventory. A committed root `wiki/**` would be
  DISCOVERED by `discover_files` (git `ls-files --cached --others` AND the walk) → enter the
  inventory hash + artifact observations + `unowned` BEFORE any doc-claim/SKIP_PREFIXES step.
  **FIX = a SCANNER-LEVEL derived-prefix exclusion of `wiki/` inside `discover_files` (both
  `_git_files` and `_walk_files`, structure/index.py)** so the book files are never in the
  scanned set at all; `SKIP_PREFIXES` is only a secondary guard for any non-hash check that still
  sees them. This scanner exclusion is W4's FIRST step (W4a) — without it the book breaks
  byte-identical.
- **SHOULD-FIX: per-page rendered-source hashes, not the whole-inventory anchor.** Reuse
  `render_generated_overview`'s narrow per-page hash (hash only the fields the chapter renders),
  NOT `build_atlas_*`'s whole `source_inventory_hash`, or every chapter restales on any unrelated
  fact move.
- **OPEN DECISION before W4 (codex): root `wiki/` vs `.codas/wiki/book/`.** Root = best
  first-viewport GitHub discoverability (the user's stated intent — "我要看") but needs the
  scanner exclusion + config/CONTRACT/documents.yml registration (W7). `.codas/wiki/book/` fits
  the existing wiki model (config wiki path = `.codas/wiki`) with less churn but weaker
  discoverability. LEANING root `wiki/` per user intent; this is the first thing W4 must lock.
- **SHOULD-FIX: split W4** — W4a = scanner exclusion + book index + ONE chapter + `--verify`
  (the current `--write`/`--verify` only renders one hardcoded governance page; generalizing the
  renderer is itself work); then W5 unify; then W4b = the remaining ~24 chapters.
- **SHOULD-FIX: `wiki/` verification.** `generated_wiki_drift` is scoped to `wiki_root/generated`
  only. So `--verify` byte-compare is the book's verifier (chapters need not carry claim blocks);
  if they do, they need a new parser root — W4 must state which.
- **NIT: W7 AMENDS CONTRACT.md, not new.** CONTRACT.md:5 currently says an LLM "renders" the
  wiki; the new model is "Codas renders the book; the LLM only authors the advisory source
  prose." W7 must fix that sentence, not write a parallel doc.
