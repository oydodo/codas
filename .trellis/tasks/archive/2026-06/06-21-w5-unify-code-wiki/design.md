# Design — W5: unify code_anchor + semantic_wiki

Minimal-churn unification (planning record §UNIFY). Survivor keeps the `code_anchor`
identity; its body becomes the full-grammar logic; `semantic_wiki` retires. `semantic/` empty
→ no page migration beyond `code/openworld.md`.

## The equivalence (why this is sound)

`anchor_symbol: <C> -> <path>:<name>` (code_anchor) ≡ `defines: <C> -> <path>::::<name>`
(semantic): both assert "concept C is the top-level symbol `name` in `path`", verified by
membership in the symbol-def node set. The semantic grammar is a strict superset (adds
`calls`/`contains` + class-method node-ids `path::cls::sym`). So replacing the anchor parser
with the semantic parser + migrating the 3 lines is behavior-preserving for the existing page.

## Concrete change map

**Adapter (`adapters/semantic.py`)** — the generic `defines/calls/contains` parser
`extract_semantic_claims` is REUSED as-is. Replace the constant `SEMANTIC_WIKI_ROOT =
".codas/wiki/semantic"` with `CODE_WIKI_ROOT = ".codas/wiki/code"`. (The offline-cache
`CORPUS_ROOT_DEFAULT` path is untouched.)

**Adapter (`adapters/wiki.py`)** — DELETE `extract_code_anchor_claims`, `CodeAnchorClaim`,
`CodeAnchorClaims`, `_parse_anchor_symbol`, the `CODE_ROOT_DEFAULT` anchor-only usage, and the
`.codas/wiki/semantic/` exclusion in `extract_wiki_claims` (line ~60). KEEP the
`.codas/wiki/code/` exclusion (the code-wiki prose stays out of the wiki-claim stream).

**Adapter (`adapters/markdown.py`)** — `SKIP_PREFIXES`: drop `.codas/wiki/semantic/`, keep
`.codas/wiki/code/`.

**Context (`facts/context.py`)** — `code_anchor_claims()` now returns `SemanticClaims` by
calling `extract_semantic_claims(repo, <wiki>/code, self.files)`. DELETE `semantic_wiki_claims()`
and the `SEMANTIC_WIKI_ROOT`/`CodeAnchorClaim`/`CodeAnchorClaims` imports + `__all__` entries.
KEEP `semantic_corpus_claims()` (offline W3 cache) + `SemanticClaims` import.

**Policy (`policies/code_anchor.py`)** — REPLACE `check_code_anchor`'s body with the
`check_semantic_wiki` logic (node universe = symbols ∪ call endpoints ∪ path/dir ancestors via
`_add_path_nodes`; resolve `defines/contains` subject ∈ nodes, `calls` (subject,object) ∈
edges; WARNING; total-key sort). Keep the function NAME `check_code_anchor` + check_id
`code-anchor`. Move `_add_path_nodes` here. DELETE `policies/semantic_wiki.py`.

**Wiring (`app/check.py`)** — drop the `check_semantic_wiki` import + its `findings.extend`.
Keep the `check_code_anchor` extend.

**Config (`.codas/policies.yml`)** — DELETE the `semantic_wiki` entry; update the `code_anchor`
description to the full grammar (defines/calls/contains; note the widened scope + that the name
persists). No id/key rename → governance.md + any golden output unaffected. [codex: policy_registry
derives the id from the FUNCTION name `check_code_anchor` → `code_anchor`, not from check_id, so
keeping the key is correct; the `semantic_wiki` entry MUST be deleted in the same change or
policy_registry reports declared-but-unimplemented.]

**Contract (`CONTRACT.md`)** — [codex SHOULD-FIX] the authoring spec still says
`anchor_symbol`-only (lines ~18-25 + ~42-51). Update both the bullet and the "Rules for
code-wiki pages" section to the `defines/calls/contains` node-id grammar verified by
`code_anchor`. Use placeholder tokens only (`<path>::::<symbol>`) so no real-path doc_claim is
created; re-verify check 0 + byte-identical after the edit (CONTRACT.md doc_claims ARE hashed).

**Committed page (`.codas/wiki/code/openworld.md`)** — migrate the 3 anchors:
```
anchor_symbol: open-world gap manifest -> src/codas/facts/openworld.py:open_world_gaps
anchor_symbol: reverse-reachability impact (open-world consumer) -> src/codas/app/impact.py:compute_impact
anchor_symbol: the code-wiki anchor verifier -> src/codas/policies/code_anchor.py:check_code_anchor
```
→
```
defines: open-world gap manifest -> src/codas/facts/openworld.py::::open_world_gaps
defines: reverse-reachability impact (open-world consumer) -> src/codas/app/impact.py::::compute_impact
defines: the code-wiki structural-claim verifier -> src/codas/policies/code_anchor.py::::check_code_anchor
```
The self-anchor target symbol `check_code_anchor` is UNCHANGED (we keep the name) → it still
resolves. Update the page's prose mention of "anchor_symbol" → the new grammar. Prose is
out-of-hash so this is byte-identical-safe for the inventory; the claims are policy-time facts.

## Determinism / invariants

- §17: parser/policy make no model call. §11: policy consumes ScanContext only.
- byte-identical: the `code/` page is out-of-hash (SKIP_PREFIXES + extract_wiki_claims
  exclusion both keep `.codas/wiki/code/`), so rewriting its claim lines does NOT move the
  inventory. PROVE with an inventory diff before/after the page edit (R4).
- open-world: WARNING-only, no hard gate (unchanged).
- No `openworld.py` public-symbol change → no anchor-to-source fact_coupling triggered.
- duplicate_implementation: `_add_path_nodes` exists in exactly one module after the move
  (semantic_wiki.py deleted) — verify no second copy.

## Tests

- `tests/test_code_anchor.py` — rewrite to the `defines/calls/contains` grammar (it already
  tested anchor resolution; now tests defines/calls/contains resolution against a synthetic
  ctx). Fold in the meaningful cases from `test_semantic_wiki.py`.
- `tests/test_semantic_wiki.py` — DELETE (merged).
- `tests/test_codas_check.py` — orchestration: one `check_code_anchor` spy; remove the
  `check_semantic_wiki` patch + the spy from the asserted tuple.
- Parity: a test asserting `check_code_anchor` on the REAL repo returns 0 findings (the 3
  migrated defines resolve) + the suite's existing inventory-determinism tests cover R4.

## Risks

- Missing a dangling import of a retired symbol → ImportError. Grep `SEMANTIC_WIKI_ROOT`,
  `CodeAnchorClaim`, `extract_code_anchor_claims`, `check_semantic_wiki`, `semantic_wiki_claims`
  across src + tests after the change; full suite catches it.
- The `code_anchor` name now spans the full grammar (mild misnomer) — accepted per the
  planning record (minimal churn beats a broad rename); documented in docstring + policies.yml.

## Review outcomes

- **Codex DESIGN review** (1 SHOULD-FIX): CONTRACT.md still documented `anchor_symbol`-only →
  FOLDED (updated both code-wiki sections to the defines/calls/contains node-id grammar).
- **Codex IMPL review = APPROVE-WITH-NITS.** Core all LGTM (traversal block intact via
  `posixpath.normpath`, the semantic resolution body preserved under `check_code_anchor`,
  registry clean, byte-identical, CONTRACT.md yields only the two existing `.codas/*.yml`
  doc-claims). Two NITs:
  - NIT1 (program.yml W5 line future-tense) → FIXED in the P8 chain.
  - NIT2 (`_norm_node` accepts a single-colon bare path like `src/a.py:foo`, the old
    anchor_symbol target syntax, which CONTRACT no longer documents) → **DECLINED with
    rationale**: (a) no correctness risk — such a token is never in the node set, so it never
    falsely resolves (it warns "does not resolve"); (b) warn-on-malformed surfaces a migration
    typo BETTER than silently skipping the claim (a hard reject → `""` → claim dropped → no
    feedback); (c) `:` is legal in a POSIX path, so a hard reject could drop a legitimate (if
    unusual) bare-path node. Keeping the permissive parse is the safer, more helpful behavior.

## Stray-artifact note

A 0-byte `path:name` file appeared in the repo root mid-task (a one-off shell redirect
artifact — no source/test creates it; the suite does not recreate it). Removed.
