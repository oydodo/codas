# Implementation Plan - Problem-3 anchors + RepairTarget

Status: ready for review before `task.py start`.

## Preconditions

- Review `prd.md` and `design.md`.
- Confirm no one needs the untracked draft in
  `/Users/oydodo/Documents/harness-problem3-anchors-repair` merged separately; this plan is now the
  canonical task artifact in the main workspace.
- Run quick baseline:

```bash
PYTHONPATH=src python3 -m unittest
PYTHONPATH=src python3 -m codas check .
```

## Phase 1 - Parser and Config

1. Extend `CodasConfig` with `anchor_live_documents: tuple[str, ...]`.
2. Parse `anchors.live_documents` from `.codas/config.yml`.
3. Add deterministic config validation for empty/misspelled entries.
4. Build live-doc discovery:
   - files/globs only
   - `.md` and `.html` only
   - hard-exclude `.trellis/tasks/archive/**`
   - hard-exclude `.trellis/workspace/**`
5. Refactor semantic claim parsing into reusable pieces:
   - Markdown top-level `atlas:claims` fences
   - HTML `<pre data-atlas-claims>`
   - strict live-doc mode preserving malformed records
   - permissive code-wiki mode preserving current behavior

Validation:

```bash
PYTHONPATH=src python3 -m unittest tests.test_code_anchor
PYTHONPATH=src python3 -m unittest tests.test_semantic_calibrate
```

Review gate:

- Four-backtick syntax examples do not parse as active anchors.
- Code-wiki behavior remains backward-compatible.

## Phase 2 - ScanContext Seams

1. Update `ScanContext.code_anchor_claims()` to include code-wiki plus configured live docs.
2. Add `ScanContext.live_doc_anchor_claims()` for strict live-doc corpus.
3. Ensure both are policy-time facts only, never serialized into inventory.
4. Add tests proving live-doc anchors do not change inventory/hash.

Validation:

```bash
PYTHONPATH=src python3 -m unittest tests.test_code_anchor
PYTHONPATH=src python3 -m unittest tests.test_book
```

Review gate:

- Archived task docs and workspace journals stay excluded even under broad globs.

## Phase 3 - RepairTarget

1. Add repair-target helpers near `code_anchor` or a small policy-private helper module.
2. Compute best-match candidates from `ctx.fact_delta()` only.
3. Attach `meta.repair_target` to unresolved `code_anchor` findings.
4. Update console rendering to print repair target lines.
5. Extend preflight context pack with capped `repair_targets`.
6. Extend preflight human summary.

Validation:

```bash
PYTHONPATH=src python3 -m unittest tests.test_code_anchor tests.test_preflight
```

Review gate:

- RepairTarget never affects severity or finding existence.
- Human `codas check` output names likely new symbol.

## Phase 4 - Anchor-Derived Couplings

1. Introduce normalized internal obligation objects in `fact_coupling`.
2. Convert manual `.codas/claims.yml fact_couplings` to obligations.
3. Convert eligible live-doc anchors to obligations:
   - exact symbol watchers from `defines:`
   - exact call watchers from `calls:`
   - public top-level symbol watchers from file-path `contains:`
4. Emit malformed live-doc anchor errors.
5. Deduplicate manual and derived obligations.
6. Keep `.codas/wiki/code/**` advisory-only.

Validation:

```bash
PYTHONPATH=src python3 -m unittest tests.test_fact_coupling
```

Review gate:

- Broken anchor with no deterministic watched delta yields no gate error.
- No gate predicate reads RepairTarget or code-anchor resolution state.

## Phase 5 - Dogfood Migration

1. Add `anchors.live_documents` to `.codas/config.yml`.
2. Add `<pre data-atlas-claims>` block to `docs/codas-design.html` section 9.4:
   - `contains: src/codas/facts/openworld.py`
   - `defines: open-world registry accessor -> src/codas/facts/openworld.py::::world_of`
   - `defines: open-world gap manifest -> src/codas/facts/openworld.py::::open_world_gaps`
3. Remove the two openworld manual rows from `.codas/claims.yml`.
4. Update policy/program docs if generated governance text mentions source shape.
5. Do not add `WORLD_BY_FAMILY` anchor unless constants are added to symbol facts in a separate,
   explicit subtask.

Validation:

```bash
PYTHONPATH=src python3 -m codas check .
PYTHONPATH=src python3 -m codas wiki --verify .
PYTHONPATH=src python3 -m codas agents --verify .
```

Review gate:

- No loss of openworld public API coverage.
- No stale generated/wiki drift.

## Phase 6 - Full Verification

Run:

```bash
PYTHONPATH=src python3 -m unittest
PYTHONPATH=src python3 -m codas check .
PYTHONPATH=src python3 -m codas wiki --verify .
PYTHONPATH=src python3 -m codas agents --verify .
git status --short
```

Acceptance checklist:

- live-doc rename gives `code_anchor` warning with RepairTarget in JSON and console
- same rename without doc co-change gives `fact_coupling` error
- archived PRDs do not drift
- Markdown syntax examples are inert
- empty live-doc globs are findings
- gate uses deterministic fact deltas only
- tests green

## Rollback Points

- After Phase 1: parser/config changes can revert without dogfood migration.
- After Phase 3: RepairTarget is metadata-only; can revert independently if presentation is wrong.
- Before Phase 5: manual openworld rows still protect current dogfood coverage.
- After Phase 5: rollback by restoring `.codas/claims.yml` openworld rows and removing the HTML
  anchors/config entries.
