# Design — Layer 1: html doc-claim adapter + stale_html_claim

## Scope (this task = Layer 1 ONLY)

Close the "authoritative `.html` is a path/link black hole" gap. Extract repo-relative
path references from config-declared authoritative+supporting `.html` and verify they
exist — parity with the markdown `doc_claims` → `stale_claim` path. **Layer 2**
(code-identifier mention staleness — the deferred "is this `<code>spec_drift</code>` a
live symbol" judgment) is explicitly OUT OF SCOPE; it needs a claim-vs-illustrative
rule and is fuzzier. The 7 stale `spec_drift` mentions the PRD cites are a Layer-2
artifact (bare identifiers, no slash/ext) — Layer 1 does NOT catch them. Stated plainly
so the acceptance is honest.

## Grounding probe (2026-06-20, decision evidence)

- The 3 authoritative HTML docs carry **zero `<a href>`**; every path reference lives in
  a `<code>` span. So Layer 1 must read code spans (markdown's `code` kind), not links.
- Simulating extraction (reusing markdown `_normalize`/`_resolve` with the `code` keep
  filter = slash + known ext + `_PATH_RE ^[\w./-]+$`): **355 code spans → 52 kept
  path-claims → exactly 2 broken**:
  - `docs/codas-implementation-plan.html:1101 -> inventory/structure.json`
  - `docs/codas-structure-map-schema.html:290 -> .codas/inventory/structure.json`
  Both name an inventory output path Codas never writes (`codas inventory --json` goes to
  stdout; there is no `.codas/inventory/` dir). These are real stale refs — the gap's
  first live teeth. Globs (`.codas/wiki/**`), brace-expansions
  (`.../{prd,design}.md`), and commands (`codas check .`) are correctly excluded by
  `_PATH_RE` (rejects `*` `{` `}` `,` space).

## Design — mirror the wiki_claims / stale_wiki_claim pattern

The repo's established shape is one fact stream + one policy per source family
(`doc_claims`→`stale_claim`, `wiki_claims`→`stale_wiki_claim`). HTML follows suit
rather than overloading `stale_claim` — because (a) HTML claims are **config-scoped**
(only declared authoritative+supporting `.html`, unlike `.md` which is scanned wholesale)
and (b) the checkable HTML refs are `code` kind, whereas `stale_claim` deliberately
filters to `kind=="link"` (markdown code spans are illustrative). Disjoint streams →
no double-finding.

1. **`adapters/html.py::extract_html_claims(repo, files, html_sources) -> list[DocClaim]`**
   - Reuses `DocClaim`, `_normalize`, `_resolve`, `KNOWN_EXTS` from `adapters/markdown`
     by intra-`codas-adapters`-unit import (the wiki adapter already does this — ONE def,
     no `duplicate_implementation`).
   - Parser = stdlib `html.parser.HTMLParser` (deterministic, no LLM). `convert_charrefs=
     True` so `&lt;id&gt;` → `<id>` in data. Collect `<code>` inner text (kind `code`) and
     `<a href>` (kind `link`); `getpos()[0]` gives the line. Read via
     `read_text(errors="ignore")` (matches markdown).
   - **Exclude `<pre>` blocks (codex SHOULD-FIX).** Track `<pre>` open/close depth; while
     `pre_depth > 0`, a `<code>`/`<a href>` is an ILLUSTRATIVE example, not a claim — skip
     it (the HTML analogue of markdown/wiki fenced-block suppression). Probe (2026-06-20):
     all 52 kept claims today are INLINE `<code>` and ZERO are inside `<pre><code>`, so
     this excludes nothing now (both broken refs survive) while closing a real future
     false-positive (an illustrative path inside `<pre><code>`).
     - KNOWN LIMITATION (codex): excluding `<a href>` inside `<pre>` too means a future
       *intentionally normative* preformatted link would be silently skipped. Acceptable —
       a normative link belongs in flowing prose, not a `<pre>` example block; revisit if a
       real case appears.
   - `extract_html_claims(repo, files)` is given the ALREADY-SCOPED concrete `.html` file
     list by the seam (below); it just parses + normalizes. Same normalize/resolve/keep-
     filter as markdown code spans; dedup on `(source, line, path, fragment, kind)`; sort
     total key `(source, line, path, fragment, kind)`.

2. **`ScanContext.html_claims() -> tuple[DocClaim, ...]`** — memoized seam accessor.
   - **Source list (codex BLOCKER): use the normalized `CodasConfig` fields**, not
     `config.raw` — `self.config.authoritative_sources + self.config.supporting_sources`
     (loader.py:55-63 nests them under `constraint_sources`; reading `raw` literally yields
     an empty set → a silently dead gate, codex's root-cause finding).
   - **Pattern scoping (codex SHOULD-FIX): match patterns against `self.files` with
     `fnmatch`**, mirroring `config_sources`/`document_set._matches_any` — a constraint
     source may be a glob (`docs/**/*.html`), so exact-equality would miss it. Adapter
     helper `governed_html_files(files, patterns)` = `[f for f in files if f.endswith(
     ".html") and any(fnmatch(norm(f), norm(p)) for p in patterns)]`, normalizing a leading
     `./` on both sides. Distinct helper name (NOT `_matches_any`, which exists in
     document_set → `duplicate_implementation` trap). Pass the result to the adapter.
   - (`DocClaim` already re-exported from `codas.facts.context.__all__`.)

3. **inventory `html_claims` block** — `{sources, references[]}` parallel to `doc_claims`
   (these ARE facts → they DO enter inventory; ensure stable sort → byte-identical). Built
   in `build_inventory` from `ctx.html_claims()`.

4. **`policies/stale_html_claim.py::check_stale_html_claim(ctx)`** — flags every
   `ctx.html_claims()` claim with `exists is False` (BOTH kinds — the slash+ext+`_PATH_RE`
   keep-filter already restricts to real-looking paths, so unlike markdown there is no
   illustrative-code-span noise to suppress). Severity **warning** (consistent with
   `stale_claim`/`stale_wiki_claim`; HTML authority is high but a path mention is a soft
   claim). Total-key sort incl. detail. §11-clean: imports only `core.models` +
   `facts.context`, no adapter.

5. **Wiring:** declare `stale_html_claim` in `.codas/policies.yml` (warning); add dispatch
   in `app/check.py` (the Nth ctx consumer). Known dogfood ripples, all handled IN THIS
   COMMIT:
   - `policy_registry`: new `check_stale_html_claim` symbol must be declared in
     policies.yml (added) — self-consistent.
   - `fact_coupling` live coupling (new `check_*` under `src/codas/policies` REQUIRES
     `src/codas/app/check.py` co-change): the commit edits check.py → companion present →
     coupling self-satisfies → dormant once committed.
   - `test_codas_check` orchestration monkeypatch must patch `check_stale_html_claim`
     (the recurring trap — every ctx-consuming policy added breaks it otherwise).

## Dogfood prerequisite (do FIRST, same commit)

Fix the 2 stale refs in `docs/codas-implementation-plan.html:1101` and
`docs/codas-structure-map-schema.html:290` (correct the inventory mechanism wording /
drop the nonexistent `.codas/inventory/structure.json` path) so the new gate is 0 on the
clean repo. HTML produces no facts today, so editing it is inventory-neutral until the
adapter lands; with the adapter, the fix is what makes `check .` = 0.

## Acceptance

- [ ] `codas check .` = 0 on the clean repo (after the 2 doc fixes); a fixture that adds a
      broken slashed-ext `<code>` path to an authoritative `.html` makes `stale_html_claim`
      fire (warning); deterministic; inventory byte-identical across 2 runs (html_claims
      enter inventory — verify stable sort).
- [ ] §11/§17 clean (adapter behind the boundary, no LLM); policy consumes via ctx only.
- [ ] full suite green; `wiki --verify` clean.

## Deferred (documented, NOT this task)

- **Layer 2** — code-identifier mention staleness (dotted `codas.policies.X` → module
  exists; declared policy-name mentions → in policies.yml / implemented `check_*`). Needs
  a tight claim-vs-illustrative rule (product-namespace dotted paths + a known vocabulary)
  to avoid false positives. The 7 `spec_drift` HTML mentions are the motivating case.
- **Audit-residue naming nits** (from the 2×2 doc pass): `structure_drift` name overload,
  `--verify` "stale" wording, design.html §16 policies.yml example omitting wired STATE
  detectors, advisory-vs-gated `must_update_if_changed` marking. An L2 term-consistency
  check would automate these; left for L2.
- **Format question** (HTML adapter vs migrating authoritative specs to governed `.md`):
  Layer 1 keeps HTML rendering while closing the path gap, so migration is unnecessary for
  this gap; revisit only if HTML maintenance cost rises.
