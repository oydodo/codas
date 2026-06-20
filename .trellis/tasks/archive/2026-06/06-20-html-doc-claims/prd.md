# Govern authoritative .html docs: html doc-claim adapter (+symbol-mention staleness)

## Status

PLANNING / backlog — surfaced 2026-06-20 (user: "任何源文件都应该被追踪"). A real
governance gap exposed while reconciling `spec_drift` → `fact_coupling` by HAND across the
HTML docs: that manual reconcile is exactly the drift Codas should catch but cannot.

> **Scope amendment (2026-06-20, supersedes the combined acceptance below):** this task
> ships **Layer 1 only** (path/link existence). See `design.md`. The 7 stale `spec_drift`
> `<code>` mentions are a **Layer 2** artifact (bare identifiers, no slash/ext) and are NOT
> in scope; Layer 1's acceptance (a broken slashed-ext path in authoritative `.html` fires
> `stale_html_claim`; 0 on the clean repo) supersedes the "7 mentions caught" criterion for
> THIS task. Layer 2 remains a documented follow-up.

## The gap (with live teeth)

`.codas/config.yml` declares `docs/codas-design.html`, `docs/codas-implementation-plan
.html`, `docs/codas-structure-map-schema.html` AUTHORITATIVE. The Structure Map owns them
(`codas-docs`, `structure-schema-doc`) and points `must_update_if_changed` at them. But
Codas extracts **zero facts/claims** from them:

- `codas.adapters.markdown` (doc_claims) scans `**/*.md` only; `codas.adapters.wiki` scans
  `.codas/wiki/**/*.md`. There is no `.html` reader. → HTML path/link refs are invisible.
- Even for `.md`, `stale_claim` verifies LINK/path claims, not code-identifier mentions: a
  `<code>spec_drift</code>` symbol/policy-name mention is treated as illustrative (deferred
  since P2). → a deleted/renamed symbol named in prose drifts unseen.

**Live proof (2026-06-20):** after retiring `spec_drift`, 7 stale `spec_drift` mentions
remain in the HTML (4 in design.html, 3 in implementation-plan.html), including
current-tense errors ("changed_paths substrate ... for spec_drift" — it now feeds
`fact_coupling`). `codas check .` is 0 and blind to all of them.

## Requirements (two layers)

**Layer 1 — html doc-claim adapter (parity with .md).** `codas.adapters.html` extracts
path/link claims from authoritative `.html` (parse `<a href>` + `<code>` spans; the same
keep-filter as markdown: a slashed path with a known extension, or a link; glob/illustrative
refs excluded) → feed the existing `doc_claims` (or an `html_claims`) stream → `stale_claim`
verifies existence. Deterministic, no LLM, behind the adapter boundary (§11), consumed via
`ScanContext`. Scope to config-declared authoritative/supporting `.html` (not every html).

**Layer 2 — code-identifier staleness (the harder, deferred gap; applies to .md too).**
Verify code-identifier mentions in authoritative docs against symbol/inventory facts:
- dotted module refs (`codas.policies.X`) → module exists in the file set;
- declared policy-name mentions (`fact_coupling`, etc.) → present in `policies.yml` /
  implemented `check_*`.
Needs a precise rule for "this code span is a CLAIM vs illustrative" to avoid false
positives (the reason P2 deferred it). Candidate: only verify dotted paths under the
product namespace + names in a known vocabulary (policy ids, CLI commands, unit ids).

## Acceptance criteria

- [ ] Layer 1: `codas check .` surfaces a broken path/link ref in an authoritative `.html`
      (proven by a fixture that adds one); 0 on the clean repo; deterministic; inventory
      byte-identical discipline (html claims are facts → they DO enter inventory, like
      doc_claims; ensure stable sort, no nondeterminism).
- [ ] The 7 stale `spec_drift` HTML mentions are caught (Layer 2) or the docs are corrected
      and a fixture proves the gate. Decide whether the historical P5 mentions are
      legitimately exempt (history) vs current-tense errors (must fix).
- [ ] §11/§17 clean; no LLM in the extraction/verification.

## Notes / decisions to make

- **Format question:** the deeper fix may be to author authoritative specs in `.md` (already
  governed) rather than `.html`. Weigh an HTML adapter vs a docs→md migration. HTML was
  likely chosen for rendering; an adapter keeps that while closing the gap.
- Layer 1 is well-bounded and high-value (closes "HTML is a black hole for paths"); Layer 2
  is fuzzier (the claim-vs-illustrative judgment) and should be scoped tightly to avoid false
  positives. Recommend shipping Layer 1 first.
- Relates to: `stale_claim` (the consumer), the markdown adapter (the pattern to mirror).

## Audit residue (2026-06-20, from the Drift/Staleness 2×2 doc pass)

A parallel doc audit (workflow) catching drift/stale conflations also surfaced these
lower-value *naming* nits — left unfixed, exactly the class an html adapter (L1) + a
term-consistency check (L2) would catch automatically rather than by manual grep:
- `structure_drift` (policy + `structure/drift.py` module + several doc rows) names a
  placement/boundary check with "drift" — orthogonal to the change-governance DRIFT
  quadrant; a reader merges the two senses.
- `--verify` "stale"/"freshness" wording in README.md, CONTRACT.md, design.html overloads
  "stale" (it is a byte-compare regeneration gate, not the STALE quadrant).
- design.html §16 policies.yml example lists planned policies but omits the wired STATE
  detectors (stale_wiki_claim/generated_wiki_drift/policy_registry) — internally stale vs
  the §11.1 wired set; an L2 policy-name-vs-wired-set check would flag it.
- Several `must_update_if_changed` mentions don't mark themselves advisory-vs-gated.
