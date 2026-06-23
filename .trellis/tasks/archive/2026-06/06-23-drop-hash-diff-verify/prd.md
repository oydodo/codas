# drop-hash + unified diff verification

Retire the whole-inventory hash as the freshness mechanism; verify every committed derived
artifact by re-render + byte-compare (diff), the way `wiki/` book + `AGENTS.md` already do.

Context + reasoning: `docs/codas-architecture-decisions.md` §2/§4 (committed `c656b0b`).
Source dialogue: handoff `.trellis/workspace/oydodo/handoff-2026-06-23-four-tasks.md` task ①.

## Problem

A generated artifact = `render(facts + prose + renderer)`. The whole-inventory
`inventory_hash` only fingerprints **facts** (prose lives out-of-inventory; the renderer is
code) → it is an INPUT fingerprint that **misses prose + renderer changes**. The book +
AGENTS.md already verify by **re-render + byte-compare** (compares actual OUTPUT → covers all
three inputs). Today's split (whole-hash for the pack, narrowed/scoped-hash for the generated
page, diff for the book) is inconsistent and the hash path is both **over-wide** (any code
edit re-stamps unrelated artifacts → churn) and **under-covering** (blind to prose/renderer).

## Requirements

- `generated_wiki_drift` verifies by re-render + byte-compare instead of comparing a pinned
  `source_inventory_hash`. Reuse the book's diff precedent (`app/book.py:295`).
- Stop embedding `source_inventory_hash` in `render_generated_overview` (`app/wiki.py` ~470
  narrowed-hash; pack whole-hash at ~172/376).
- Determinism is preserved as a **run-twice TEST** (canonical serialization stays; build the
  inventory twice → identical bytes), not as a production freshness hash.
- `inventory_hash` (`core/provenance.py`) is retained ONLY as an optional audit/receipt
  fingerprint, never as the freshness gate. (Decision point (a) below.)
- Byte-identical invariant for the whole repo still holds; `--verify` stays clean.

## Decision points (resolve with user at design review)

- (a) keep `inventory_hash` as an audit receipt, or drop entirely? (lean: keep as audit-only)
- (b) generated-page byte-compare gated per-commit (current) vs CI-only? (lean: keep gated —
  it is cheap)

## Acceptance Criteria

- [ ] `generated_wiki_drift` is a re-render+byte-compare check; no freshness path reads a
      pinned hash.
- [ ] No derived artifact stores `source_inventory_hash` for freshness.
- [ ] Run-twice determinism test exists and passes.
- [ ] `PYTHONPATH=src python3 -m codas check .` → 0 findings; `codas wiki --verify` clean;
      `unittest discover -s tests` green.
- [ ] A prose-only change to a `.codas/wiki/code/*.md` page is now CAUGHT by the gate
      (regression test — proves the old hash blind spot is closed).

## Notes

- gate-semantics task → **codex DESIGN review BEFORE impl** (iron rule). codex-MCP stalls →
  fall back to Claude-native adversarial reviewer.
- Recommended FIRST of the 4 (most certain, de-risks, prerequisite for the multi-lang book).
- Effort ~1-2 days. Key files: `core/provenance.py`, `app/wiki.py`,
  `policies/generated_wiki_drift.py`, `app/book.py:295` (precedent).
- Gate-run command on this source checkout: `PYTHONPATH=src python3 -m codas check .`.
