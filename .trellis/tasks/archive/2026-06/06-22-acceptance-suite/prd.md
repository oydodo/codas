# Acceptance suite — whole-product verification charter

## Problem

563 unit tests verify components in isolation; nothing proves the **product** meets the PRD
end-to-end. Two real bugs (CLI argparse `dest` collision; `exec VAR=val` hook bug) shipped
past the unit suite — they lived only on the integration surface and were caught by manual
dogfood, not a test. There is no traceability from tests to PRD §22 Acceptance / §25 Normative.

## Goal

A whole-product acceptance suite (`tests/acceptance/`) layered ABOVE the unit tests: drive
Codas through public entry points only (`run_check`, `python -m codas …` CLI, `--verify`, the
hook envelope) against synthetic whole repos, organized into 11 modules (M0–M10) covering the
8 PRD pillars, with each assertion traced to a PRD requirement.

This task is the **charter / DESIGN** only. It produces `design.md` and the adversarial DESIGN
review. The modules ship as separate child tasks per the build sequence.

## Requirements

- `design.md` captures: the 11-module architecture (M0–M10), the shared `tests/_repo.py`
  golden-repo builder API, the M2 conformance-matrix case table (20 policies), M3
  waiver-suppression + exit-code semantics, M1 fact-extraction golden + open-world soundness,
  M9 CLI-subprocess wiring, PRD traceability, CI integration, build sequence, open questions.
- Adversarial DESIGN review completed (codex if usable, else Claude-native multi-lens), its
  blockers folded into `design.md`.

## Acceptance Criteria

- [x] `design.md` complete (all sections above present).
- [x] DESIGN review done (codex, NEEDS-REWORK); 6 blockers verified against source + folded
      into `design.md` §11. B6 (waiver suppression unimplemented) carried to a separate product
      task.
- [x] Build sequence agreed. Follow-ups: `06-22-acceptance-golden-repo` (step 1, golden builder)
      + `06-22-waiver-suppression` (the B6 product gap — build waiver→finding suppression).

## Notes / Non-goals

- No test code in this charter task (design only).
- Not replacing the unit suite (acceptance is the coarse end-to-end layer above it).
- Implementing the 5 planned policies is out of scope — they stay registry-inert.
