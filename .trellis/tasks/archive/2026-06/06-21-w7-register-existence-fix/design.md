# Design — W7 (register book root + config-aware existence fix + CONTRACT)

Concrete change map for the implementing session. The CORE is the config-aware existence fix
(R1–R3); registration is a config knob; CONTRACT is docs. Gate-semantics → codex DESIGN review
(this plan) THEN codex IMPL review after build.

## 1. Config knob + the shared predicate

- `.codas/config.yml` `wiki:` block → add `book_root: wiki`.
- `src/codas/structure/index.py`: replace the hardcoded `_DERIVED_OUTPUT_PREFIXES = ("wiki",)`
  with a resolver `derived_output_prefixes(raw_config) -> tuple[str,...]` (mirrors
  `workspace_roots`): reads `raw["wiki"]["book_root"]`, defaults to `("wiki",)`, empty/missing
  → `()`. Generalize `_is_derived_output(path)` → `is_derived_output(path, prefixes)` (public),
  the SINGLE authority.
- Thread the prefixes to every scan entry point that calls `filter_to_roots`:
  - `discover_files(repo, roots, derived_prefixes=())` and `filter_to_roots(files, roots,
    derived_prefixes=())` gain the param (default `()` so non-config callers are unaffected;
    BUT the real scans must pass the config value).
  - `head_snapshot` (`facts/snapshot.py`) + `build_artifact_index` + `build_inventory` pass it
    through. Source of the value = config (the inventory/scan already loads config).
  - CAUTION (codex W4a Q1): the prefixes must reach BOTH `discover_files` AND `head_snapshot`
    (the HEAD fact baseline) — they both funnel through `filter_to_roots`, so threading the
    param there covers both, but VERIFY every `filter_to_roots` caller passes it.

## 2. The four existence sites (the leak fix)

Each resolves a claim/role TARGET to `exists`; guard each with the shared predicate BEFORE the
`Path.exists()`/glob, returning `False` for a derived-output target:
- `adapters/markdown.py` (doc_claims) — add a `derived_prefixes: tuple[str,...] = ()` param;
  `exists = False if is_derived_output(path, derived_prefixes) else (repo/path).exists()`.
- `adapters/html.py` (html_claims) — same param + guard.
- `adapters/wiki.py::_exists` (wiki_claims, literal + glob) — same guard at the top (covers
  both forms; a `wiki/*` glob short-circuits).
- `structure/inventory.py:134` (documents role) — guard before `(repo/document.path).exists()`.
- §11: adapters receive `derived_prefixes` as a DATA param from `facts/context.py` (which holds
  config and already calls these adapters) — NO adapter imports config. `is_derived_output` is
  a `structure.index` helper; adapters importing it is allowed (no forbidding dep rule, no
  cycle — confirmed in W5's adapter→structure precedent).

## 3. Registration (no documents.yml role)

The config `wiki.book_root` IS the registration: the book is a DERIVED output (like
`.codas/wiki/generated/`), not a source DOCUMENT. Do NOT add a `documents.yml` role (it would
re-introduce a 4th existence dependency AND `document_set` would demand a scanner-excluded
file exists). Optionally add a README "see `wiki/`" pointer — now SAFE (the fix forces it
absent, so it never enters the hash); keep it OUT of scope unless trivial.

## 4. CONTRACT.md

- Amend the sentence (~line 6): "Codas **grounds** the wiki (verified facts), an LLM
  **renders** it, and Codas **verifies** it." → "Codas **grounds** the wiki (verified facts)
  and **renders** the generated pages + the `wiki/` book DETERMINISTICALLY (no model); an LLM
  only **authors** the advisory source prose (out of the hash); Codas **verifies** the
  structural claims + byte-compares the render."
- Add a "## Verification contract" section: the 4 artifact classes (FEED ephemeral / GENERATED
  `--verify`+generated_wiki_drift / WIKI-PAGES advisory-prose-out-of-hash + verified claims via
  code_anchor & stale_wiki_claim / CACHE gitignored) + the verifier-routing table.
- CONTRACT.md is a SUPPORTING doc that IS scanned (doc_claims) — keep edits to prose +
  placeholder tokens so no NEW real-path doc_claim appears; re-verify check 0 + byte-identical.

## 5. Tests

- KEEP `LatentLeakGuardTests` (it asserts no claim targets the book — after the fix, a claim
  COULD target it and resolve absent; the guard's purpose shifts to "the leak stays closed").
  Reframe: ADD `test_book_reference_does_not_move_inventory` — write a transient governance
  `.md` (a supporting doc) that links `wiki/index.md`; assert the claim's `exists` is False AND
  `build_inventory` is byte-identical with vs without the book dir on disk.
- `test_adapters` `wiki/concepts/a.md` fixture: the synthetic repo uses default config (no
  `book_root` set in its `CodasConfig(raw={})`). DECISION (codex to confirm): the default
  `derived_output_prefixes({})` should be `()` (NO reservation when no config), so the existing
  `test_adapters` fixture (raw={}) is UNAFFECTED — the reservation only applies when a real
  config sets `book_root` (Codas's own config does). This DISSOLVES the W4a over-reach cleanly:
  the predicate fires only for repos that declare a book. (NB this differs from today's scanner
  which reserves `wiki/` unconditionally; W7 makes BOTH config-driven, so the scanner ALSO stops
  reserving `wiki/` when unconfigured — verify no current test depends on the unconditional
  reservation; Codas's config will set `book_root: wiki` so its own behavior is unchanged.)
- Determinism: full suite + `codas inventory` byte-identical 2× + `wiki --verify` clean +
  the book chapters re-render identically (config knob doesn't change the render).

## 5b. Codex DESIGN-review corrections (FOLDED — the implementing session builds to THESE)

- **OPEN DECISION #1 RESOLVED → default `("wiki",)`, NOT `()`.** Flipping the default to `()`
  breaks THREE `tests/test_artifact_index.py` tests (`test_wiki_book_excluded_in_walk_fallback`
  :101, `test_filter_to_roots_drops_derived_output` :126, `test_wiki_book_excluded_git_path`
  :136) — they use config-less synthetic repos that rely on the unconditional reservation. Keep
  `derived_output_prefixes({}) == ("wiki",)`. The opt-out is `wiki.book_root: ""` → `()` (a user
  with real non-book `wiki/` docs disables the reservation explicitly). This MAINTAINS the
  shipped W4a scanner behavior + adds the existence-layer + adds an opt-out — strictly better,
  minimal test churn. Over-reach is mitigated by the opt-out, not eliminated by default (Codas
  has defaulted-reserved since W4a; consistency wins). Codas's own `config.yml` sets
  `book_root: wiki`.
- **BLOCKER → move the `test_adapters.py` fixture.** With `("wiki",)` default,
  `tests/test_adapters.py:39-42`'s `wiki/concepts/a.md` fixture now resolves `exists=False` and
  `assertTrue(claims.get("wiki/concepts/a.md"))` fails. Rename that test's `wiki/` → `docs/`
  (three `_write` calls + assertions). The test is about relative-link resolution; the dir name
  is incidental.
- **SHOULD-FIX → 5th leak site: `adapters/markdown.py::_resolve` (lines ~114, 118).** Its
  `.exists()` calls choose repo-relative vs source-relative resolution → they set `claim.PATH`
  (not just `claim.exists`). A backtick `` `wiki/x.md` `` span in a SUBDIR `.md` doc would get a
  different serialized `path` with vs without the book on disk → byte non-identical. GUARD
  `_resolve`: before the repo-relative `.exists()`, if `is_derived_output(repo_rel, prefixes)`
  skip it and fall through (treat as not-present-at-repo-root). Inert today; name + fix it with
  the other four.
- **SHOULD-FIX → `build_artifact_index` literal-unit `exists` (structure/index.py).** The
  `else: exists = (repo/prefix).exists()` block is an unguarded prospective site (inert — no
  unit has `path: wiki`; the registration is config-only, NOT a structure unit). Guard it
  preemptively (`if is_derived_output(prefix, prefixes): exists=False`) OR add a test asserting a
  derived-output unit path resolves absent.
- **SHOULD-FIX → thread the prefixes through EVERY `filter_to_roots` caller.** `_walk_files`
  (index.py:152, called by discover_files) AND `head_snapshot` (snapshot.py — add a third param
  `derived_prefixes`, passed from `ScanContext.head_snapshot()` via
  `derived_output_prefixes(self.config.raw)`) AND `build_artifact_index`. Default the param to
  `("wiki",)` so a non-config caller keeps the shipped behavior; the real scans pass the config
  value. Enumerate + update all callers; the suite catches a miss.
- **CONTRACT.md guard — SPECIFIC rule:** a backtick code span becomes a `DocClaim` iff it has
  BOTH a slash AND a known extension (`.md/.py/.html/...`). So do NOT write `` `wiki/<x>.<ext>` ``
  anywhere in CONTRACT.md; `` `wiki/` `` (no extension) and prose "the book at `wiki/`" are
  SAFE. (`CONTRACT.md` is root-level so `_resolve` disambiguation doesn't bite there, but the
  claim-creation rule still applies.)
- **NIT (confirmed not-a-site):** `structure_drift.py:46` `.exists()` is check-time, NOT
  serialized into the inventory → not a leak. `stale_claim`/`stale_wiki_claim`/`stale_html_claim`
  read the pre-computed `.exists` field, never re-resolve → not leak sites. The four+1 list is
  complete.

## 6. Open decisions — RESOLVED

1. **Default prefixes = `("wiki",)`** (codex). Opt-out via `wiki.book_root: ""`. See §5b.
2. **Threading** (not module-state) confirmed §11-clean + correct (codex). Thread through
   `filter_to_roots` + `_walk_files` + `head_snapshot` + `build_artifact_index`; default the
   param to `("wiki",)`; real scans pass `derived_output_prefixes(config.raw)`.
3. **`_PRODUCT_PREFIX` cross-repo knob = SEPARATE task** (not W7). Different blast radius
   (changes what the tree/book/pack COVER, not existence). Leave as a flagged backlog item.

## 7. Acceptance — see prd.md. Make-or-break = R2 (leak closed: a book reference doesn't move
the inventory) + R3 (opt-out, no over-reach), proven by the new byte-identical test.
