# W7: register the book root + CONTRACT amend + config-aware claim-existence fix

## Goal

Make the `wiki/` book a GOVERNED, safely-referenceable artifact (not an orphan dir), and land
the claim-existence fix deferred from W4a — CONFIG-AWARE, so it closes the latent
byte-identical leak without over-reaching onto a user's real `wiki/` docs.

Three strands:
1. **Register the book root via CONFIG** (a `wiki.book_root` knob), not a documents.yml role
   (a role would itself activate the leak — see below).
2. **Config-aware existence fix** — the FOUR raw-`Path.exists()` sites that resolve a
   claim/role TARGET bypass the `filter_to_roots` book exclusion, so a governance doc that
   references the book would bleed its on-disk presence into the inventory hash.
3. **CONTRACT.md** — amend the "an LLM renders it" sentence + add the verification-contract /
   verifier-routing doc (the wiki-layer plan's W7 deliverable).

## Background — the leak (proven latent in W4a, activates here)

`wiki/` is excluded at the FILE SCANNER (`filter_to_roots`, `_DERIVED_OUTPUT_PREFIXES`), but
claim/role existence is resolved by raw filesystem calls that bypass it:
- `src/codas/adapters/markdown.py` doc_claims `exists=(repo/path).exists()`
- `src/codas/adapters/html.py` html_claims `exists=(repo/path).exists()`
- `src/codas/adapters/wiki.py::_exists` wiki_claims (literal + glob)
- `src/codas/structure/inventory.py:134` documents-role `exists=(repo/document.path).exists()`

So ANY governance doc (README link, CONTRACT mention, or a documents.yml role) that targets a
path under the book flips its `exists` on the book's presence → into the inventory hash. W4a
proved it INERT (no current reference) and DEFERRED the fix because a blanket "wiki/ absent"
rule OVER-REACHES (false-missing on a user's real `wiki/` docs; it broke `test_adapters`). W7
is where we add a reference, so W7 must fix it — CONFIG-AWARE (the escape hatch dissolves the
over-reach: a user can move/disable the book root).

## Design (to be codex-reviewed before the next session implements)

- **Config knob:** `wiki.book_root` (default `"wiki"`). A helper `book_root_prefixes(raw)` (like
  `workspace_roots`) returns the reserved derived-output prefixes from config. Empty/unset →
  no reservation (a user not using the book keeps their `wiki/` fully governed).
- **One shared predicate:** generalize `structure/index._is_derived_output(path)` to take the
  config prefixes; make it the SINGLE authority used at every layer that resolves a path→fact:
  - scanner: `filter_to_roots` (thread the prefixes in, replacing the hardcoded
    `_DERIVED_OUTPUT_PREFIXES` constant — keep `("wiki",)` as the default).
  - the 3 claim adapters: a claim target under a derived prefix resolves `exists=False`
    WITHOUT a `Path.exists()` call. §11-safe: the adapter receives the prefixes as a DATA
    param from `context.py` (which holds config), never importing config.
  - `inventory.py` documents-role existence (`:134`): same guard before `Path.exists()`.
- **Registration:** the config knob IS the registration (the book is a DERIVED output, like
  `.codas/wiki/generated/`, not a source DOCUMENT). Do NOT add a documents.yml role for it
  (avoids the 4th leak site + the document_set policy demanding a scanner-excluded file). A
  README "see `wiki/`" pointer is now SAFE (the existence-fix forces the link absent) and
  OPTIONAL.
- **CONTRACT.md:** amend line ~6 ("an LLM **renders** it") → "Codas **renders** the book
  deterministically; an LLM only **authors** the advisory source prose (out of the hash), and
  Codas **verifies** the structural claims." Add the verification-contract model (FEED /
  GENERATED / WIKI-PAGES / CACHE) + a verifier-routing table (concept_page→stale_claim;
  canonical_source/evidence/sync_target→stale_wiki_claim; doc_claims→stale_claim/stale_html;
  generated→generated_wiki_drift + `--verify`; code-wiki claims→code_anchor; book→`--verify`).
- **Over-reach test that broke W4a:** `test_adapters`'s `wiki/concepts/a.md` fixture — with the
  config-aware fix, the synthetic repo has NO `wiki.book_root` set (default applies). DECIDE in
  design: either (a) the default reserves `wiki/` so that test moves its fixture to a
  non-reserved dir, or (b) the existence guard only fires when book_root is explicitly
  configured. Codex to weigh. (Leaning (a) — consistent with the W4a scanner reservation,
  which already makes that fixture's `wiki/` scanner-invisible; the fixture name was incidental.)

## Requirements

- R1 — `wiki.book_root` config knob (default `"wiki"`); one shared config-driven derived-output
  predicate used by the scanner + all four existence sites.
- R2 — a governance doc/role referencing a path under the book resolves `exists=False` and does
  NOT move `codas inventory` (the latent leak is CLOSED, not just inert).
- R3 — a user can opt out (book_root unset → their `wiki/` is governed normally); no over-reach.
- R4 — CONTRACT.md amended (the renders/authors sentence + the verification-contract/routing
  table). Book registered via config (no documents.yml role).
- R5 — `LatentLeakGuardTests` still passes; ADD a test: a doc claim targeting `wiki/index.md`
  yields `exists=False` and leaves the inventory byte-identical with/without the book on disk.

## Acceptance Criteria

- [ ] Editing/adding a governance reference to the book does NOT change `codas inventory`.
- [ ] `wiki.book_root` config-drives the reservation at scanner + 4 existence sites (one predicate).
- [ ] A repo with `book_root` unset governs its `wiki/` normally (opt-out works).
- [ ] CONTRACT.md: "Codas renders, LLM authors source prose" + verification-contract/routing table.
- [ ] `codas check` == 0; inventory byte-identical 2×; full suite green; `wiki --verify` clean.
- [ ] New + existing leak-guard tests pass; the `test_adapters` `wiki/` fixture decision resolved.

## Notes

- Gate-semantics (scanner config + adapter/inventory existence + config schema) → the next
  session MUST run codex DESIGN review first (this plan is pre-reviewed) THEN codex IMPL review.
- ADJACENT / candidate to fold or defer: the cross-repo blocker `_PRODUCT_PREFIX="src/codas/"`
  hardcoded in `app/wiki.py` (book/tree/pack empty on non-Codas layouts). Same "config-drive a
  hardcoded path" shape as book_root — could ride along, or stay a separate task. DECIDE in design.
- After W7 = W8 packaging (pip/pipx + README PYTHONPATH doc-lie fix).
