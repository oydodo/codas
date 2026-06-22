# Acceptance harness — tests/_repo.py golden-repo builder (step 1)

## Problem

The whole-product acceptance suite (charter:
`.trellis/tasks/archive/2026-06/06-22-acceptance-suite/`) needs a way to build synthetic,
VALID, zero-finding Codas repos on demand, so each later case = golden + one mutation. No shared
fixture exists today (49 hand-rolled `_write/_ctx` helpers, 300 ad-hoc tempdirs). This task is
the PURE ENABLER prerequisite — no product behavior change.

## Goal

`tests/_repo.py`: a profile-based golden-repo builder + a `GoldenRepo` handle, proven to produce
a `run_check` = 0-findings repo. Plus a first acceptance test asserting the golden is clean.

## Requirements

- `GoldenRepo` handle: `write(relpath, content)`, `remove(relpath)`, `commit(msg)` (git
  add+commit), `check() -> CheckReport` (in-process `run_check`), `cli(*args) ->
  CompletedProcess` (`python -m codas …`), `kinds() -> set[(check_id, severity)]`.
- `build_golden(tmp, *, profile="check") -> GoldenRepo` produces a MINIMAL, valid, git-committed
  repo that `run_check` returns ZERO findings for.
- PROFILES (charter Q2): start with `check` (the minimal gate-clean repo). Structure the builder
  so `wiki`/`agent`/`full` profiles can be added later without rework.
- Honor the review folds that bear on the builder:
  - **B3:** the `check` profile must NOT include a `.` repo-root catch-all unit (it would own
    every file and make missing_structure_owner untriggerable). Every file present must be owned
    by a NON-root unit; no file left unowned in the clean baseline.
  - **B1:** policy_registry scans the TARGET repo's `src/codas/policies/` tree. The golden must
    not self-fail policy-registry. Decide per charter Q1 fold (lean: keep the golden's registry
    surface minimal — no `src/codas/policies/` defs AND no policy declarations that demand them;
    the policy_registry/severity-catalog CASES will run against the REAL repo, not the golden).
    The golden's `.codas/policies.yml` must be internally consistent with whatever check_*
    surface it ships (empty↔empty is fine).
  - git: `commit()` enables the fact_coupling case (working-tree-vs-HEAD diff) later.

## Acceptance Criteria

- [x] `build_golden(tmp).check().findings == []` (the keystone — a genuinely clean synthetic
      repo through the REAL `run_check`). Proven by `test_golden_is_clean_in_process`.
- [x] `GoldenRepo.cli("check", ...)` runs the real entrypoint and returns exit 0 on the golden.
- [x] `git status` clean inside the built golden after `commit()`.
- [x] Builder is profile-structured (`_PROFILES` dict; unknown profile raises; adding one = a
      dict entry, no refactor).
- [x] `unittest discover -s tests` green (568, +5); `codas check .` 0; inventory byte-identical
      2×; agents/wiki --verify clean. tests/_repo.py + tests/acceptance/ under `codas-tests`.

## Notes

- Placement (charter Q8): `tests/_repo.py` + any fixtures under `tests/acceptance/fixtures/`,
  both in the `codas-tests` unit. Run `codas check .` after adding to confirm no structure-map
  update needed.
- This is the foundation only; M2 matrix / M1 facts / M9 CLI are separate follow-up tasks built
  on this.
