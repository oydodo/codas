# codas doctor: installation diagnostic command (P6)

## Goal

Implement the stubbed `codas doctor` — a read-only diagnostic of a Codas installation,
distinct from `codas check` (governance policies). Per the design doc (§ doctor):
"config, Trellis presence, removed-prototype leftovers." doctor answers "is Codas set
up correctly here?" so an agent / CI / hook can diagnose a broken `.codas` BEFORE (or
when) `check` can't run. First P6 enforcement-integrations slice; the gates (S2+) shell
out to `check`, and `init` (later) is doctor's inverse (scaffold what doctor reports
missing).

## Requirements

- `app/doctor.py::run_doctor(repo) -> list[Diagnostic]`; `Diagnostic{name, status, detail}`
  with `status` ∈ `ok|warn|fail`. Deterministic fixed order; read-only.
- Diagnostics:
  - `git_repo` — repo is a git work tree (`git rev-parse`); else **warn** (Codas runs
    without git, but diff/hooks need it).
  - `config` — `.codas/config.yml` exists + parses (`load_codas_config`); missing/parse
    → **fail** (nothing else can be trusted).
  - `policies` — `.codas/policies.yml` exists + parses; else **fail**.
  - `waivers` — `.codas/waivers.yml` exists + parses; else **fail** (`check` requires it).
  - `structure_map` — `.codas/structure.yml` exists + parses (`load_structure_map`);
    else **fail**.
  - `program_plan` — `.codas/program.yml` optional: absent → **warn**; present+parse
    error → **fail**.
  - `documents` — `.codas/documents.yml` optional: absent → **warn**; parse error →
    **fail**.
  - `trellis_context` — if config declares a `workflow.root`, that dir must exist; else
    **fail** (configured-but-missing); no workflow configured → **ok** (n/a).
  - `legacy_prototype` — the P0-removed prototype paths (`src/harness_guard`,
    `scripts/harness-guard`) must be ABSENT; present → **fail** (leftover).
- `codas doctor [repo] [--json]`: human report + `--json`. **Exit 1 if any `fail`**,
  else 0 (warns don't fail the gate). Replaces the `parser.error` stub.
- Config is loaded once; if it fails, dependent diagnostics (`trellis_context`) degrade
  gracefully (detail "config did not load") rather than crash.

## Acceptance Criteria

- [ ] `codas doctor .` on this repo → all ok/warn (program/documents present → ok), exit 0.
- [ ] Fixtures: missing config → fail+exit1; broken yaml → fail; leftover prototype → fail;
      absent optional program.yml → warn (exit 0); configured-but-missing trellis root → fail.
- [ ] `--json` deterministic; human report readable. §11 (app→loaders, no adapter) /
      §17 (no LLM) clean. `codas check .` still 0 (doctor symbols owned by codas-app).
- [ ] Full suite green; inventory byte-identical (doctor is a command, not a fact).

## Implemented (2026-06-20) + codex impl review folded

Shipped `app/doctor.py::run_doctor` + `doctor_has_failures` + `codas doctor [--json]`
(replaces the stub). 9 tests; `codas doctor .` healthy exit 0; 289 tests; check 0;
inventory byte-identical; --verify clean.

Codex impl review — **APPROVE (0 blockers)**, all SHOULDs/NIT folded:
- **Config-aware required-vs-optional (SHOULD 1+2):** `program.yml`/`documents.yml` are
  declared authoritative in config, so their absence is `check`-failing
  (`config_sources` error). Doctor now fails (not warns) when an optional file is absent
  *and* declared authoritative; genuinely-undeclared absence still warns. Both branches
  tested.
- **Deeper Trellis (SHOULD 3):** `trellis_context` now checks `<workflow.root>/tasks`
  exists (mirroring `check_trellis_context`'s hard error), not just the root, and only
  when `workflow.adapter == trellis`.
- **Stale docs (SHOULD 4):** `docs/codas-implementation-plan.html` + `codas-design.html`
  updated — doctor is implemented (P6 S1), not a stub; `init` remains the pending P6
  setup command.
- **NIT:** `test_this_repo_has_no_failures` pins `_REPO` instead of `Path.cwd()`.

Design lives in this PRD (low-risk slice mirroring existing loader/policy patterns;
went prd → implement → codex impl review, no separate design review).

## Out of scope

- `codas init` (the scaffold — next P6 slice; doctor's inverse).
- The enforcement gates themselves (pre-commit/pre-push/Action/Trellis — later slices).
- Deep semantic validation (that is `check`'s bootstrap policies); doctor is presence +
  parse + setup, deliberately lighter.
