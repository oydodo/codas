# W4a: render wiki/ book skeleton (scanner exclusion + index + 1 chapter + --verify)

## Goal

First build of the P8 readable wiki book. Render a deterministic, GitHub-browsable
`wiki/` chapter-book — for W4a: the scanner-level exclusion that keeps the book OUT of
the byte-identical inventory, plus `wiki/index.md` + ONE subsystem chapter + `--verify`.
W4b renders the remaining ~24 chapters once the renderer is generalized and proven here.

## Why W4a is its own task

The wiki-layer plan (`archive/2026-06/06-21-wiki-layer-plan/design.md`) + the codex
plan-review correction: the original "hash-excluded like `.codas/wiki/generated/`" wording
was a FALSE precedent — `generated/` is excluded only via `exclude_under=` passed by the
wiki builders, NEVER by the default `codas inventory`/`check` scan. A committed root
`wiki/**` would be DISCOVERED by `discover_files` (git `ls-files` AND the walk) → enter the
inventory hash + artifact observations + `unowned` BEFORE any SKIP_PREFIXES step. So the
book breaks byte-identical UNLESS a scanner-level exclusion lands FIRST. That exclusion is a
gate-semantics change (it alters what the inventory sees) → codex DESIGN review required.

## Requirements

- **R1 — lock the location: root `wiki/`** (the user's "我要看" / GitHub first-viewport
  intent). `.codas/wiki/book/` rejected (weaker discoverability). Registration in
  config/CONTRACT/documents.yml is W7; W4a hardcodes a single reserved-prefix constant +
  names the debt.
- **R2 — scanner-level derived-prefix exclusion of `wiki/`** in `discover_files`
  (`structure/index.py`), covering BOTH the git path (`_git_files`) and the walk fallback
  (`_walk_files`). `wiki/` becomes a RESERVED derived-output prefix (like a build dir):
  committed but never in the scanned file set, so it never enters the inventory hash,
  artifact counts, or `unowned`. This lands FIRST, before any book file is written.
- **R3 — generalize the renderer**: today `--write`/`--verify` render ONE hardcoded
  `governance.md`. Add a book renderer (pure inventory→pages projection) producing
  `wiki/index.md` (nav + overview) + ONE subsystem chapter, reusing the narrow
  per-page rendered-source hash pattern (`_generated_pages`), NOT the whole-inventory anchor.
- **R4 — one chapter**: a chosen Structure-Map subsystem rendered as: heading + owner, a
  module→class→function tree-slice (from the knowledge tree, scoped to that unit), a
  dependency mermaid (GitHub-native fenced block, zero external deps), and the open-world
  lower-bound caveat rendered ONCE, visibly.
- **R5 — `--verify` = byte-compare** the book pages against a fresh render (chapters carry
  NO `atlas:claims` block in W4a → byte-compare is the only verifier; `generated_wiki_drift`
  stays scoped to `.codas/wiki/generated/`).
- **R6 — determinism preserved**: with `wiki/` excluded, `codas check` stays 0 and
  `codas inventory` stays byte-identical before AND after the book is written/committed.

## Acceptance Criteria

- [ ] `wiki/` is excluded at the scanner level in BOTH `_git_files` and `_walk_files` paths;
      a file under `wiki/` is absent from `discover_files`, the inventory, and `unowned`.
- [ ] `codas wiki --write` renders `wiki/index.md` + one chapter, deterministic + idempotent.
- [ ] `codas wiki --verify` is clean immediately after `--write`; flags a hand-edit/stale page.
- [ ] Each chapter pins a narrow per-page rendered-source hash; an unrelated fact move does
      NOT restale it (mirror `test_atlas_pack`'s narrow-hash test).
- [ ] The chapter renders the open-world caveat once; the dependency mermaid is GitHub-native.
- [ ] `codas check` == 0 and `codas inventory` byte-identical 2× with the book committed.
- [ ] Full test suite green; new tests for the exclusion + book render + narrow hash.

## Notes / open items pushed to later W-phases

- W5 unify `code_anchor` + `check_semantic_wiki` (do while `semantic/` empty).
- W4b render the remaining ~24 chapters (renderer generalized here).
- W7 register `wiki/` in config/documents.yml + amend CONTRACT.md:5 ("Codas renders the
  book; the LLM only authors advisory source prose"); lift the hardcoded book-root constant
  into config.
- W6 prose fill (host agent authors per-chapter "why" into `.codas/wiki/` source).
