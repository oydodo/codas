# Implement — drop-hash + unified diff verification

Execution checklist. Derived from design.md §4 (codex-verified surface). Work in the worktree
`../harness-drop-hash-diff-verify` on branch `feat/drop-hash-diff-verify`.

Gate command (this source checkout): `PYTHONPATH=src python3 -m codas check .`
Tests: `PYTHONPATH=src python3 -m unittest discover -s tests`
Verify: `PYTHONPATH=src python3 -m codas wiki --verify .`

## Step 1 — drop the page hash (code)
- [ ] `src/codas/app/wiki.py`: `render_generated_overview` — remove `source_inventory_hash`
      param + the `f"source_inventory_hash: {…}"` line (445); `_generated_pages` — delete the
      `rendered_source` + `source_hash` computation (470-481), call
      `render_generated_overview(inventory)`; fix docstrings (392, 460-468, 504).
- [ ] `src/codas/adapters/wiki.py`: keep `GeneratedPage.source_inventory_hash` parse TOLERANT
      (parse-but-ignore at 273/295) so an old committed page still loads; the field is simply
      no longer required by the gate. (Do NOT hard-remove the parse — backward-compat for a
      not-yet-regenerated page.)
- [ ] `src/codas/policies/generated_wiki_drift.py`: structural predicate (53) `has_block and
      page.source_inventory_hash and page.claims` → `has_block and page.claims`; drop the
      "with a source_inventory_hash" wording in the error message (60) + docstring (26, 32-37).
- [ ] `src/codas/facts/context.py:224`: docstring mention only.

## Step 2 — co-change governed docs (§4b — MUST, or stale_*/coupling fire)
- [ ] `.codas/policies.yml:70`: rewrite the `generated_wiki_drift` description — drop "must
      embed … with a source_inventory_hash"; state freshness is verified by `codas wiki
      --verify`, the gate verifies the claims block + fact-consistency.
- [ ] `.codas/program.yml:143,144,145`: update the D3a/b/c/d narrative — the committed page
      carries `atlas:claims` (unit/roadmap) verified for fact-consistency; freshness =
      `--verify` byte-compare. Drop the "carrying source_inventory_hash" page claims (keep the
      pack/tree `source_inventory_hash` mentions — those stay).
- [ ] `CONTRACT.md:35,38,163`: drop the `source_inventory_hash` line requirement (35/38) +
      the routing-table token (163); state the block needs ≥1 claim, freshness via `--verify`.
- [ ] `docs/codas-design.html:1127`: drop "及一个 source_inventory_hash" from the generated
      page description.
- [ ] `docs/codas-implementation-plan.html:627,750,756,876,1095`: drop page-hash mentions;
      KEEP grounding-pack/tree `source_inventory_hash` mentions (those are the audit hash).

## Step 3 — regenerate + reclassify
- [ ] `PYTHONPATH=src python3 -m codas wiki --write .` → regenerates
      `.codas/wiki/generated/governance.md` without line 53 (the hash line).
- [ ] `src/codas/core/provenance.py`: docstring — `inventory_hash` = audit/provenance receipt
      (pack/tree emit stamp), NOT a committed-artifact freshness mechanism.

## Step 4 — tests
- [ ] `tests/test_generated_wiki_drift.py` (42,92,129,136,143,156,164): drop the
      `source_inventory_hash` fixture lines + the missing-hash-error assertion (156-160);
      keep unit/roadmap fact-consistency tests.
- [ ] `tests/test_generated_sections.py` (37,70,87,92): drop hash-present assertions.
- [ ] ADD: run-twice determinism test (build inventory twice → identical bytes).
- [ ] ADD: regression — a unit field change rerenders the page → `verify_generated_sections`
      flags it (freshness rides in bytes, no hash needed).
- [ ] ADD: backward-compat — a committed page still carrying a `source_inventory_hash:` line
      parses (tolerant) and `--write` rewrites it clean.
- [ ] pack/tree hash tests (`test_atlas_pack.py`, `test_knowledge_tree.py`): UNCHANGED — assert
      they still pass (proves pack/tree audit hash untouched).

## Step 5 — verify gate (all must pass)
- [ ] `PYTHONPATH=src python3 -m codas check .` → "No Codas findings."
- [ ] `PYTHONPATH=src python3 -m codas wiki --verify .` → clean (no stale pages).
- [ ] `PYTHONPATH=src python3 -m unittest discover -s tests` → all green.
- [ ] byte-identical: run inventory/render twice → identical (run-twice test covers it).

## Rollback points
- Step 1 breaks tests → revert wiki.py/policy, re-read the render path.
- Step 2 trips a stale_* finding → grep the flagged path, that doc still names the page hash;
  fix wording. (This is the codex-flagged trap — expect it if a §4b file is missed.)
- Step 3 `--write` produces unexpected diff → the render still embeds the hash somewhere;
  back to Step 1.

## Finish
trellis-check → trellis-update-spec → commit on branch → merge to main → `task.py archive`.
