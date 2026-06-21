# W6: weave authored why-prose into the wiki/ book chapters

## Goal

Turn the structure-only book skeleton (W4) into a book worth reading: `codas wiki --write`
weaves the host-agent-authored "why" PROSE from `.codas/wiki/code/<unit-id>.md` into each
rendered chapter `wiki/<unit-id>.md`. Skeleton-first, prose incremental — a chapter with no
source prose still renders (structure only); a chapter with prose gains an `## Overview`.

Two parts: (1) the deterministic WEAVE MECHANISM (this code change); (2) AUTHORING the prose
for the chapters (LLM/host-agent work, §17 — done as a parallel fan-out, ongoing-fillable).

## Mechanism (the code)

- Source: `.codas/wiki/code/<unit-id>.md` — hand-authored advisory markdown. Its PROSE
  (everything OUTSIDE any fenced ```` ```atlas:claims ```` block) is the "why". The same page
  may ALSO carry `defines/calls/contains` claims (verified by `code_anchor`) — book weaves the
  prose, `code_anchor` verifies the claims; clean separation.
- Render: `_render_chapter` gains the prose; inserts a `## Overview` section with the woven
  prose AFTER the meta (Path/Owner/Kind) and BEFORE the open-world banner — only when prose
  exists. `project_book(inventory, prose_by_unit)` stays a PURE projection; `book_pages(repo)`
  gathers `{unit_id: prose}` off disk (strip the claims fence) and passes it in.
- Determinism / §17: the book is `f(facts + prose bytes)`. The prose is LLM-authored but, once
  committed in `.codas/wiki/code/` source (OUT of the inventory hash), the render is
  deterministic — Codas renders with NO model. `wiki/` stays scanner-excluded; `--verify`
  byte-compares (a prose edit restales the chapter -> regenerate). No policy / scanner / gate
  change → renderer-only (codex IMPL review; no DESIGN review).
- Book root for the code-wiki source = `.codas/wiki/code` (hardcoded like BOOK_ROOT; W7
  config-drives it).

## Requirements

- R1 — `--write` weaves `.codas/wiki/code/<unit-id>.md` prose into `wiki/<unit-id>.md` as
  `## Overview`; a unit with no source page renders unchanged (skeleton).
- R2 — the claims fence is stripped from the woven prose (machine data, not human text); a
  page that is claims-only weaves nothing.
- R3 — determinism: `--write` idempotent, `--verify` clean, inventory byte-identical
  (prose source + book both out-of-hash).
- R4 — author the "why" prose for the 10 code-unit chapters (accurate, grounded in each unit's
  facts + source), seeding the readable book. Incremental: remaining concept pages later.

## Acceptance Criteria

- [ ] A chapter with a source prose page shows `## Overview` with that prose; one without
      shows the skeleton (no Overview, no dead section).
- [ ] `code_anchor` still verifies any claims on the prose pages; `codas check` == 0.
- [ ] `--write` idempotent; `--verify` clean; inventory byte-identical 2×.
- [ ] The 10 code-unit prose pages authored; the book reads as a narrative + structure.
- [ ] New tests: weave present/absent, claims-fence stripped, byte-identical preserved.

## Notes

- The prose pages double as `code_anchor` claim sources — authors may add `defines/calls/
  contains` claims to anchor the prose to real symbols (verified, code->doc drift caught).
- Next after W6 = W7 (register book root + CONTRACT + the deferred existence-fix) / W8 packaging.

## Review outcome

Mechanism = renderer-only (no gate change) → no codex DESIGN review; codex IMPL review run.
**Codex IMPL: no BLOCKER.**
- SHOULD-FIX (fence closer too loose — a ` ```python ` line could close a claims block early)
  → APPLIED: tightened the close to a BARE fence (`stripped.strip("`") == ""`) in BOTH
  `book.py::_strip_claims_block` AND `semantic.py::extract_semantic_claims` (renderer/parser
  aligned). Byte-neutral on the current pages (no nested fences).
- NIT (authored prose with a peer `## Modules & symbols` heading or stray fence could corrupt
  a chapter's structure) → DECLINED with rationale: a content-mutating lint would need
  fence-awareness (riskier than the rare ugly-render it guards); the 10 pages are verified
  clean (no `##`/`#` headings, exactly the one `atlas:claims` fence each); determinism +
  `--verify` hold regardless. Revisit if it bites.

## Authoring (the prose)

Authored all 10 code-unit pages via a parallel fan-out (workflow `w6-author-chapter-prose`,
10 agents, each grounded in its unit's source). Each `defines:` anchor was validated against
the real symbol set before writing (0 of 29 dropped — all resolve), so `code_anchor` is clean.
Remaining: concept pages + prose refinement, incremental.
