# PRD — P5 D2: stale-wiki-claim policy

## Context

P5 (`program:P5:wiki-reconciliation`) exit criterion: **"Wiki claims are verified
against repo facts."** D1 shipped the wiki claim parser (`wiki_claims` inventory
block + `ScanContext.wiki_claims()`). D2 ships the policy that turns those parsed
claims into verified governance facts — emitting a finding when a wiki claim cannot
be verified against repo facts.

**Authority.** Plan §2: "A wiki claim becomes a governance fact only when Codas can
verify its evidence **and authority**." §2.1: "Wiki and indexes help navigation;
they do not become fact sources by themselves." `codas-product.md` Duplicate Risks:
"Do not let generated wiki pages become higher authority than facts and explicit
constraint sources." §5 Wiki module output: "stale wiki findings."

## What D2 verifies (and what it deliberately leaves to `stale_claim`)

`stale_claim` already flags broken Markdown **links** (`kind == "link"`) — including
the wiki `## Concepts` links (`concept_page`). It does **not** check code-span
paths. The wiki's `canonical_source`, `evidence` and `sync_target` claims are all
**code spans**, so nothing verifies them today. D2 fills exactly that gap, plus the
authority dimension `stale_claim` never had:

1. **Authority** (`canonical_source`, literal paths): a wiki "Canonical Source" must
   actually be a constraint source — declared `authoritative` or `supporting` in
   `.codas/config.yml`. A wiki page that elevates a path to "canonical" which config
   does not treat as a constraint source is the §2 over-claim ("wiki must not become
   higher authority than constraint sources") → finding. Glob canonical sources
   (e.g. `.trellis/tasks/**`) are navigational pointers to a tree, not per-artifact
   authority assertions → exempt from the authority check (existence-verified only).
2. **Existence** (`canonical_source`, `evidence`, `sync_target`): the code-span
   path the wiki references must exist on disk (the D1 `exists` fact; globs via
   `repo.glob`). Missing → finding. `concept_page` (links) existence is deliberately
   **not** re-checked — `stale_claim` already owns broken-link findings (no
   double-finding).

Severity **warning** (consistent with `stale_claim`; the wiki is a `supporting`
authority surface, so drift is a warning, not a hard gate).

## Requirements

1. New `src/codas/policies/stale_wiki_claim.py`:
   `check_stale_wiki_claim(ctx: ScanContext) -> list[Finding]`:
   - reads `ctx.wiki_claims()` and `ctx.config` (authoritative + supporting
     sources); imports **no** adapter (consumes facts via the seam, per §11).
   - authority: for each `canonical_source` claim with `path_kind == "literal"`
     whose `path` is not matched by any config authoritative/supporting pattern
     (glob-aware via the existing `_matches_any`) → warning.
   - existence: for each `canonical_source` / `evidence` / `sync_target` claim with
     `exists == False` → warning.
   - deterministic: findings sorted on a total key (source, line, path, check facet).
2. `app/check.py`: wire `check_stale_wiki_claim(ctx)` after the other ctx policies.
3. `.codas/policies.yml`: declare `stale_wiki_claim` (severity warning).
4. `tests/test_codas_check.py`: add `check_stale_wiki_claim` to the orchestration
   test's monkeypatch set (every ctx-consuming policy must be patched there).

## Acceptance criteria

- `check_stale_wiki_claim` on a fixture wiki flags: a canonical source absent from
  config authority; a canonical source matched only by a config **glob** (verified,
  no finding); a missing evidence/sync path; and does **not** flag a `concept_page`
  link (left to `stale_claim`).
- On this repo: **0 findings** (all 11 literal canonical sources are matched by a
  config authoritative/supporting pattern — incl. `.trellis/spec/...` via the
  `.trellis/spec/**/*.md` glob; `.trellis/tasks/**` is glob-exempt; every wiki
  code-span path exists).
- `codas check .` → "No Codas findings"; full suite green; `codas inventory`
  byte-identical; `inventory.unowned` unchanged.

## Non-goals

- `concept_page` link existence (owned by `stale_claim`) and concept-page
  *registration* (is the linked concept a known structure/documents fact) — a later
  facet.
- `sync_target` ↔ structure-map `must_update_if_changed` **reverse-pointer**
  consistency (the wiki says "update X when Y changes"; does structure.yml agree?) —
  a richer cross-fact check deferred to a follow-up; D2 verifies sync_target
  existence only.
- Glob-vs-glob authority subsumption (is the wiki glob a subset of a config glob) —
  globs are existence-verified, authority-exempt.
- The `codas wiki` command / generated sections — that is D3.
- Promoting `_matches_any` out of `policies/document_set.py` — D2 imports it
  (intra-`codas-policies` unit); a shared-location refactor is deferred.
