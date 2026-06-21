# Design — W4a: wiki/ book skeleton

Builds on the locked decisions in `archive/2026-06/06-21-wiki-layer-plan/design.md`
(two-part split; book = rendered skeleton + woven prose; chapter-book; skeleton-first) and
its "## Codex PLAN review — corrections". This design is the concrete W4a slice.

## 1. Location (LOCKED) — root `wiki/`

`wiki/` at repo root. Rationale: GitHub first-viewport discoverability = the user's stated
intent ("我要看"). `.codas/wiki/book/` rejected (buried, weaker discoverability).
W4a introduces a single reserved-prefix constant; config/documents.yml/CONTRACT
registration is W7 (debt named in code + program.yml).

## 2. The scanner exclusion (the load-bearing change)

**Problem (codex):** a committed root `wiki/**` is DISCOVERED by `discover_files` — both
`_git_files` (`git ls-files --cached --others --exclude-standard`, the book is tracked) and
`_walk_files` — so it enters the inventory hash + artifact observations + `unowned` BEFORE
any `SKIP_PREFIXES`/doc-claim step. That breaks byte-identical.

**Fix — a scanner-level derived-output exclusion in `filter_to_roots` (the shared funnel):**

[REVISED per codex Q1 BLOCKER — the exclusion seam moved from `discover_files` to
`filter_to_roots`.] `discover_files` is NOT the only scan entry point: `head_snapshot`
(`facts/snapshot.py:56`, feeding `fact_delta`) lists HEAD blobs and calls ONLY
`filter_to_roots`, bypassing `discover_files`. A `wiki/*.py` would then enter the HEAD fact
snapshot independently. BOTH `discover_files` (`index.py:81`) and `head_snapshot`
(`snapshot.py:56`) — and `build_artifact_index` (`index.py:140`) — funnel through
`filter_to_roots`. So that is the ONE chokepoint to exclude at.

- New module constant: `_DERIVED_OUTPUT_PREFIXES = ("wiki",)` — repo-relative dir prefixes
  that are Codas-RENDERED committed output, never scanned input. Conceptually distinct from
  `_IGNORE_PATHS` (`.codas/receipts`, `.codas/cache` = local/regenerable, walk-only) — the
  book is COMMITTED but DERIVED.
- New predicate `_is_derived_output(path)`: true if `path == prefix or path.startswith(prefix
  + "/")` for any prefix in `_DERIVED_OUTPUT_PREFIXES`. Prefix-boundary safe: `wiki/` must NOT
  swallow a hypothetical `wikipedia.py` at root.
- Apply INSIDE `filter_to_roots` (drop derived-output paths before/within the root select), so
  EVERY scan that funnels through it — inventory `discover_files`, the HEAD `head_snapshot`,
  and `build_artifact_index` — honors the reserved prefix in one place. No caller of
  `filter_to_roots` legitimately wants to see `wiki/` (the book is read directly by `--verify`
  via `Path.read_text`, never through this funnel).
- ALSO prune the dir in `_walk_files` (add the prefix to the dir-prune step alongside
  `_IGNORE_PATHS`) so the walk fallback doesn't descend `wiki/` needlessly — correctness is
  already guaranteed by the `filter_to_roots` predicate; this is the consistency/perf mirror.

**Why exclude a committed dir from the hash (determinism argument):** the book is a pure
function of (facts + `.codas/wiki/` source prose). Including it in the inventory would be
(a) self-referential — the book renders facts, and its bytes would then feed the hash that
the book pins — and (b) churn-amplifying: every prose edit would move the inventory hash.
Excluding it keeps the inventory a function of SOURCE only; the book's own freshness is
checked separately by `--verify` byte-compare. §17 holds: Codas renders with no model.

**Sequencing:** R2 (the exclusion) merges and is tested BEFORE any `wiki/` file is written.
Since no root `wiki/` exists today, the exclusion is a no-op on the current tree → inventory
stays byte-identical at the exclusion commit; the book lands in the same task but the
inventory never observes it.

## 3. The book renderer (`src/codas/app/book.py`, new)

Pure inventory→pages projection, mirroring `_generated_pages`. No ScanContext, no LLM, no
adapter import (§11). Consumes the same `run_inventory(repo, exclude_under=(_GENERATED_DIR,))`
inventory (and AFTER the R2 exclusion lands, `wiki/` is excluded by `filter_to_roots`, so the
book never feeds its own render — no self-reference).

- `project_book(inventory) -> dict[relpath, str]` — pure; returns `{ "wiki/index.md": ...,
  "wiki/<chapter>.md": ... }`.
- Chapter selection for W4a: ONE Structure-Map unit (propose `codas-source`, the product
  root unit — richest tree-slice; final pick stated in implement notes). The renderer is
  written to take a unit and slice the knowledge tree by `unit_id`, so W4b is "loop over all
  units", not a rewrite.
- **Narrow per-page hash:** each page embeds (in an HTML comment, NOT an `atlas:claims`
  block) a hash over ONLY the fields it renders — reuse the `_generated_pages` pattern
  (`inventory_hash(json.dumps(rendered_source, sort_keys=True, ...))`). An unrelated fact
  move (e.g. a unit's `artifact_count`) must NOT restale the chapter. The hash rides in the
  bytes, so `--verify` byte-compare catches both stale-hash and hand-edits with no separate
  bookkeeping.

### index.md
- `# <repo> — Atlas Book (generated)` + GENERATED banner.
- Overview: short deterministic line + the units table (id/path/owner) as nav, each linking
  to its chapter file (only the chapter(s) that exist in W4a are live links; the rest are
  listed plain — honest, no dead links). Open-world caveat line.

### chapter `wiki/<unit>.md`
- `# <unit_id>` heading + owner + path.
- **Tree-slice**: module→class→function from `project_atlas_tree(inventory)`, filtered to
  nodes whose `unit_id` == this unit, rendered as a nested bullet list (deterministic sort
  by node-id). Methods are call-endpoint-derived (lower bound).
- **Dependency mermaid**: a GitHub-native ` ```mermaid ` fenced `graph LR` of this unit's
  first-party import edges (module→target), labels neutralized. [codex Q4: do NOT import
  `views._mermaid_label` from `book.py` — `views.py` already imports `app.wiki`, so
  `wiki→book→views→wiki` is a cycle. FIX = extract the label helper to a neutral
  `app/render_util.py` (no app imports) and have BOTH `views.py` and `book.py` import it;
  this also avoids the `duplicate_implementation` same-private-name error from inlining a
  second `_mermaid_label`.] Zero external script (matches the S1 no-CDN rule).
- **Open-world banner** rendered ONCE: "Structure shown is a sound lower bound (open-world);
  an absent function/edge is not proof of absence." (same caveat `codas impact`/views use).
- NO `atlas:claims` block in W4a → byte-compare is the sole verifier; if a later phase adds
  claim blocks to chapters, it must register a new parser root (stated, not done here).

## 4. CLI wiring

`--write` / `--verify` extend to ALSO render the book pages (one render-all of committed
machine-rendered output). `verify_generated_sections` + the book verifier both byte-compare;
`--verify` returns 1 if EITHER the governance page or any book page is stale. Keep the
existing `_generated_pages` governance path untouched; add a parallel `_book_pages(repo)`
and fold both into write/verify. No new flag (the plan: "`codas wiki --write` renders it").

[codex Q5 SHOULD-FIX] All book read/write pins explicit `encoding="utf-8"` + `newline="\n"`
(write) / `encoding="utf-8"` (read) — platform-default encoding/newline would break
byte-identical on Windows/some-locales. Harden the EXISTING `write_generated_sections` /
`verify_generated_sections` the same way (no byte change on macOS/Linux where the default is
already utf-8/`\n`, so `--verify` stays clean). [codex Q5 NIT] Sort the written-page list AND
the stale-page list by repo-relative path for deterministic CLI output once governance + book
pages are combined.

## 5. Verification routing (unchanged contracts)

- `generated_wiki_drift` policy: stays scoped to `.codas/wiki/generated/` ONLY. The book has
  no claim block, so it is NOT in this policy's universe — correct.
- Book freshness: `codas wiki --verify` byte-compare (opt-in / CI), same as generated pages.
- Always-on `codas check`: unaffected — the book is scanner-excluded, so no new finding.

## 6. §11 / §17 / invariants checklist

- §11: `app/book.py` consumes the inventory dict (pure), never imports `codas.adapters`;
  the scanner change is in `structure/index.py` (discovery layer), no boundary cross.
- §17: no model in the render path.
- byte-identical: exclusion lands first; inventory is a function of source only; book hash is
  narrow per-page.
- No new public symbol in `openworld.py` → no anchor-to-source fact_coupling triggered
  (couplings are openworld.py-only; verified in claims.yml).
- `duplicate_implementation`: new private helpers get unique names (grep `^def _name`).
- orchestration test: no new ctx-consuming policy added → `test_codas_check` unaffected.

## 7. Tests

- `test_index.py` (or extend): a file placed under `wiki/` is absent from `discover_files`
  via BOTH the git path and the walk fallback (monkeypatch `_git_files -> None` to force the
  walk); `wiki/` excluded from inventory + `unowned`; prefix-boundary (`wikipedia.py` at root
  NOT excluded).
- **[codex Q1 regression] HEAD-snapshot exclusion**: a `wiki/foo.py` blob in the HEAD tree is
  excluded from `head_snapshot` (it funnels through `filter_to_roots`), so it cannot enter the
  `fact_delta` baseline. Assert via `filter_to_roots(["wiki/foo.py", "src/codas/x.py"], (".",))`
  dropping the `wiki/` path.
- `test_book.py` (new): `project_book` deterministic + idempotent; index lists the chapter;
  chapter has the tree-slice + a `mermaid` block + the open-world banner once; narrow-hash
  test (unrelated fact move → page bytes unchanged); `--write` then `--verify` clean; a
  hand-edit → `--verify` flags it.
- Dogfood: `codas check` == 0 and `codas inventory` byte-identical 2× after writing the book.

## 8. Acceptance — see prd.md. The make-or-break is R2 (exclusion before book) + R6
(byte-identical preserved). W4b (remaining chapters) and W5 (unify) follow.

## 8b. Implementation decisions (recorded during build)

- **Chapter pick = `codas-app`** (`src/codas/app`): the richest first chapter (classes,
  methods, a dense first-party import mermaid) and dogfood-fitting (the renderer `book.py` +
  `render_util.py` live there, so they self-appear). 24 units total; W4b loops the rest.
- **Absent-unit graceful skip**: `project_book` renders a chapter only for `_CHAPTER_UNITS`
  that EXIST in the repo, skipping absent ones — so `--write`/`--verify` run on ANY repo (a
  synthetic test repo lacking `codas-app` must not crash). The index links ONLY rendered
  chapters (never a dead link). The chapter set stays Codas-self-specific until W7 lifts it
  into config.
- **No embedded freshness hash in book pages** (refines design §3): the book renders ONLY
  stable source facts (unit id/path/owner, the tree-slice, import edges), never volatile
  observations, so byte-compare alone restales a chapter EXACTLY when its source moves — the
  narrow-hash goal (codex Q2) is met by construction, no hash line needed.
- **3.9-safe LF pin = `write_bytes`/`read_bytes`** (not `write_text(newline=...)`, which is
  3.10+): pins UTF-8 + LF, byte-exact compare. Applied to the book AND hardened the existing
  `write/verify_generated_sections` (no byte change to the committed `governance.md` on
  macOS/Linux, so `--verify` stays clean).

## 8c. Codex IMPL review verdict (3 BLOCKER + 2 SHOULD-FIX) — resolved

- **3× BLOCKER (claim-existence leak)** — the doc/wiki/html adapters resolve a claim
  TARGET's existence with a raw `Path.exists()`/`repo.glob()`, bypassing `filter_to_roots`.
  If a governance doc references a path under the committed `wiki/` book, that boolean would
  bleed the book's presence into the inventory hash. VERDICT: the leak is **real but LATENT**
  — proven by a with-vs-without-book inventory diff (IDENTICAL: no current claim targets the
  book). The codex fix (force every `wiki/` path absent in the adapters) was **tried and
  REVERTED**: it OVER-REACHES — it would mark a user's real `wiki/` docs missing and emit
  false "broken target" findings (worse than the inert leak, which produces no false
  findings; it also broke `test_adapters`'s incidental `wiki/` fixture). The correct fix needs
  the **config-aware book root** and lands with **W7** (which is also when the book first gets
  referenced). To keep the latent leak from silently activating, added an **invariant guard
  test** (`tests/test_book.py::LatentLeakGuardTests`) that FAILS the moment any doc/wiki/html
  claim targets `wiki/` — forcing the W7 existence fix to land alongside the first reference.
  W4a's deliverable (the SCANNER exclusion) is airtight and byte-identical-safe as shipped.
- **2× SHOULD-FIX (orphan blind spot)** — FIXED: `verify_book` and `verify_generated_sections`
  now also flag a committed `*.md` no longer in the rendered set (a chapter dropped from
  `_CHAPTER_UNITS` lingers on disk; regenerating never removes it), so `--verify` catches the
  drift. Test: `test_verify_detects_orphan_page`.
- No findings on §11 / §17 / write_bytes LF-pin / determinism / dead-link guard.

## 9. Codex DESIGN review verdict (folded above)

Reviewed clean except one BLOCKER + 2 SHOULD-FIX + 2 NIT, ALL folded:
- **BLOCKER Q1** — exclusion seam moved `discover_files` → `filter_to_roots` (the shared
  funnel for inventory + HEAD snapshot + artifact index). §2, §7 updated.
- **SHOULD-FIX Q4** — no `app.views` import from `app.book`; extract the mermaid label helper
  to a neutral `app/render_util.py` imported by both. §3 updated.
- **SHOULD-FIX Q5** — explicit `utf-8`/`newline="\n"` on all book + generated read/write. §4.
- **NIT Q5** — sort written + stale page lists by relpath. §4.
- **NIT Q6** — design no longer present-tenses the not-yet-existing exclusion. §2/§3.
- **Q2 (narrow hash) + Q3 (write/verify fold) — LGTM**, no change.
