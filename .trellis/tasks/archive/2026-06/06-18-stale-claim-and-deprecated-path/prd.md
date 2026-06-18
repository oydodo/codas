# PRD: Stale claim and deprecated path policies

## Context

First substantive P2 governance slice on top of the P1 inventory. Two policies
declared in `.codas/policies.yml` but not yet implemented:

- `stale_claim` (severity: warning)
- `deprecated_path_used` (severity: error)

Both are **inventory/structure-direct, whole-working-tree, evidence-backed, and
deterministic** — no diff, no LLM similarity (plan §17). They are the lowest-risk
P2 policies because the facts they consume already exist:

- `stale_claim` consumes the Markdown doc-claim index (`extract_doc_claims`,
  already surfaced in `codas inventory . --json` as `doc_claims.references[]` with
  an `exists` flag).
- `deprecated_path_used` consumes the Structure Map `deprecated_paths` block
  (already parsed by `load_structure_map` into `StructureMap.deprecated_paths`).

Authority:
- `docs/codas-implementation-plan.html` §10 Policy Roadmap — `stale_claim` First
  Implementation: "Markdown path references point to existing files."
- `docs/codas-structure-map-schema.html` §8 — `deprecated_path_used` Initial Rule:
  "New files must not be added under deprecated or removed paths." Finding:
  "Error with replacement path when known."

## Goals

1. `stale_claim`: emit a warning Finding for each Markdown **link** reference
   (`[text](path)`) whose target path does not exist.
2. `deprecated_path_used`: emit an error Finding for each tracked artifact whose
   path falls under a Structure Map deprecated/removed path, including the
   replacement path when the Structure Map declares one.
3. Both wired into `codas check .` and covered by tests.
4. Dogfooding invariant preserved: `codas check .` stays at 0 findings on this
   repo after the slice (the real tree has no broken Markdown links and no files
   under removed paths). Policy behavior is proven with dedicated fixtures.

## Non-Goals (deferred to later P2 / later expansion)

- **Code-span path references** (`` `path` `` in prose). Deferred: backtick path
  mentions are routinely illustrative (e.g. `e.g. research/auth-library-comparison.md`)
  and produce false positives. §10 Later Expansion ("Symbol and fragment anchors")
  groups deeper reference checking; code-span mentions join that cut. The repo's
  only 3 `exists=false` claims today are all `kind=code` — flagging them would be
  noise (one is an `e.g.` example; two are Trellis-internal paths absent from this
  checkout).
- **Fragment / anchor existence** for links (`#anchor`). Later expansion.
- **Diff-scoped detection** ("new files under changed diff"). Whole-tree only;
  diff scoping is a later P2 expansion.
- **Glob deprecated paths**. Current deprecated_paths are literal directory
  prefixes; literal prefix match only for the first cut.
- Waiver matching / expiry enforcement (separate `waiver_valid` expansion).

## Acceptance Criteria

- `stale_claim` flags exactly the broken-**link** Markdown references; ignores
  code spans, existing links, external URLs, anchors-only, and image links.
- `deprecated_path_used` flags every tracked file under a deprecated_path prefix,
  with the replacement surfaced in the recommendation when present.
- Findings are deterministic: stable sort, no timestamps, no machine-specific
  ordering. `codas inventory` remains byte-identical across two runs.
- `codas check .` → still 0 findings on this repo.
- `PYTHONPATH=src python3 -m unittest discover -s tests` passes (new tests added).
- Dogfooding: no new artifacts outside owned Structure Units (new policy files
  land under `codas-policies`, new tests under `codas-tests` — already governed).
