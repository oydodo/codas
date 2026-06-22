# Waiver suppression — apply valid waivers to suppress findings (PRD §17 gap)

## Problem (surfaced by the acceptance-suite DESIGN review, B6)

PRD §17 / design.html promises a violation can be bypassed by a valid waiver: *"agent 不能通过
解释或忽略绕过 gate，只能修复、更新约束源或提交有效 waiver。"* The implementation does NOT do
this. `check_waivers` (`src/codas/policies/waivers.py:10-40`) only validates waiver SCHEMA
(id/reason/owner/`expires` present + `expires` not past). `run_check` (`src/codas/app/check.py:
94-109`) APPENDS waiver findings and never filters the earlier policy findings. The code admits
it: `src/codas/app/provenance.py:23` — *"waivers.yml (which suppresses findings) is out of scope
for now."* So waivers are name-only: validated, but suppress nothing.

## Goal

Make a valid, matching waiver actually SUPPRESS the finding(s) it covers, per PRD §17.

## Requirements

- A waiver entry gains a SCOPE that identifies what it covers (e.g. `check_id` + optional
  `path`/`symbol` glob). Design the match grammar (see open questions).
- `run_check` (or a layer just before severity aggregation) filters findings matched by a valid,
  unexpired waiver. Schema-invalid or expired waivers suppress NOTHING (and still emit
  `waiver-schema-invalid` / "expired" findings as today).
- A suppressed finding is RECORDED (not silently dropped) — e.g. surfaced as an advisory
  "waived" entry in the report / receipt, so the audit trail shows what was waived and by whom.
- Deterministic, no LLM (§17). Adapter-free (the waiver match is a core/app concern).
- Update the acceptance suite's `test_valid_waiver_suppresses_finding` from xfail → passing.

## Acceptance Criteria

- [ ] A valid matching waiver removes the covered finding from `codas check`; exit code reflects
      the post-suppression severity (error→1 only if an UN-waived error remains).
- [ ] Expired / schema-invalid / non-matching waiver suppresses nothing.
- [ ] Suppressed findings are auditable (report/receipt records the waiver id that covered them).
- [ ] `provenance.py:23` "out of scope" comment removed; provenance accounts for waiver state.
- [ ] check 0 · byte-identical · tests green.

## Notes / process

- GATE-ADJACENT (changes gate behavior) → adversarial DESIGN review BEFORE building.
- Open questions for the design: match grammar (check_id only? + path/symbol globs? evidence-
  path match?); where suppression runs (in run_check vs a reporting filter); how the inventory
  hash treats waiver state (waivers.yml is config = closed-world); interaction with severity
  aggregation + receipts + provenance.
- Charter + the B6 record: `.trellis/tasks/archive/2026-06/06-22-acceptance-suite/design.md` §4
  + §11.
