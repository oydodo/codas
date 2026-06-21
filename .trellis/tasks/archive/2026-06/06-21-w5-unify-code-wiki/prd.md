# W5: unify code_anchor + semantic_wiki into one code-wiki policy/grammar

## Goal

Collapse the two overlapping committed-wiki policies into ONE parser / policy / grammar.
`code_anchor` (`anchor_symbol: C -> path:name` over `.codas/wiki/code/**`) is a strict
SUBSET of `semantic_wiki` (`defines/calls/contains` over node-ids, `.codas/wiki/semantic/**`):
`anchor_symbol: C -> path:name` ≡ `defines: C -> path::::name`. Two near-duplicate machines
(both read committed advisory prose, verify code-anchored claims against the symbol/call
universe, WARNING/open-world) → one. Debt named at `.codas/policies.yml` (`semantic_wiki`
description: "the two will be UNIFIED at v1 … behind a golden parity test").

**Do it NOW because `.codas/wiki/semantic/` is EMPTY** — no committed semantic pages to
migrate, so the merge is a near-pure refactor (only the one `code/openworld.md` migrates).
Once `semantic/` accumulates pages the merge gets strictly more expensive.

## Decision (per the 06-21-wiki-layer-plan record: "keep code/ dir, retire the 'semantic' name, minimal churn")

- **Survivor = `code_anchor`** (KEEP the name/check-id/policies.yml key — minimal churn, no
  golden-output or self-anchor symbol rename) but its BODY becomes the full-grammar logic
  (today's `check_semantic_wiki`), reading `.codas/wiki/code/**`.
- **Retire** the `semantic_wiki` committed policy + its name/root: `check_semantic_wiki`,
  `policies/semantic_wiki.py`, `semantic_wiki_claims()`, `SEMANTIC_WIKI_ROOT`,
  `.codas/wiki/semantic/` exclusions, and the `anchor_symbol` keyword + the
  `extract_code_anchor_claims`/`CodeAnchorClaim`/`_parse_anchor_symbol` machinery (superseded
  by the `defines/calls/contains` parser `extract_semantic_claims`).
- **KEEP the offline W3 semantic CACHE untouched**: `.codas/cache/semantic/`,
  `semantic_corpus_claims()`, `extract_semantic_claims` (the generic grammar parser, reused),
  `app/calibrate.py`. That "semantic" name is the real W3 judge corpus — a DIFFERENT thing
  from the committed semantic WIKI being retired. Do not conflate.
- **Grammar**: the unified code-wiki uses `defines/calls/contains` over node-ids. The
  `code/openworld.md` page migrates its 3 `anchor_symbol:` lines to `defines:` (`path::::name`
  node-id form). Prose unchanged.

## Requirements

- R1 — ONE policy verifies `.codas/wiki/code/**` structural claims (`defines/calls/contains`)
  against the symbol ∪ call-endpoint ∪ path-ancestor node universe; WARNING, all-open
  (never hard-gate an open-world absence). Identical resolution semantics to today's
  `semantic_wiki`, pointed at `code/`.
- R2 — `code/openworld.md` migrated: 3 `anchor_symbol: C -> path:name` → `defines: C ->
  path::::name`. The 3 still resolve (resting 0 findings).
- R3 — all `semantic_wiki`/`anchor_symbol`-specific code retired (adapter, dataclasses,
  parser, policy file, context seam, policies.yml entry, exclusions).
- R4 — GOLDEN PARITY before/after: prove `codas check` resting result is UNCHANGED (0
  code-wiki findings before, 0 after) and the inventory is byte-identical (the `code/` prose
  is out-of-hash, so editing `openworld.md` must not move the hash).

## Acceptance Criteria

- [ ] One committed-wiki policy remains (`code_anchor`, full grammar); `semantic_wiki` gone.
- [ ] `code/openworld.md` uses `defines:`; the 3 claims resolve; `codas check` == 0.
- [ ] Inventory byte-identical (before vs after the page migration AND run-to-run).
- [ ] Orchestration test (`test_codas_check`) updated: one code-wiki spy, not two.
- [ ] `test_semantic_wiki.py` retired/merged into `test_code_anchor.py`; full suite green.
- [ ] No dangling import of any retired symbol (`SEMANTIC_WIKI_ROOT`, `CodeAnchorClaim`, …).

## Notes

- Gate-semantics change (delete a policy, rewire check.py, edit policies.yml) → codex DESIGN
  review FIRST, then codex IMPL review.
- A future code-wiki page MAY now use `calls`/`contains` (the grammar supports it); current
  usage is `defines` only. The `code_anchor` name persists though the scope widened —
  documented in the policy docstring + policies.yml.
- Next after W5 = W6 (prose fill).
