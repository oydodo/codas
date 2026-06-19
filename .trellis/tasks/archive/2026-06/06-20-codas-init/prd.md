# codas init: scaffold a .codas skeleton (P6 S3)

## Goal

Implement `codas init` — scaffold a minimal valid `.codas/` skeleton in a repo without
one (the inverse of `codas doctor`). Last P6 setup slice; pairs with doctor (init
creates exactly the doctor-required set).

## Requirements

- `app/init.py::scaffold(repo, *, force=False) -> ScaffoldResult{written, skipped}` +
  CLI `codas init [repo] [--force]`. App-layer only (no adapter, §11; no LLM, §17).
- Scaffolds the doctor-required four: `.codas/config.yml`, `policies.yml`,
  `structure.yml`, `waivers.yml`. Each a loadable template:
  - config declares the four as authoritative, no workflow adapter (so doctor's Trellis
    check is n/a), no dogfooding protocol (a fresh `check` emits one advisory warning,
    not an error);
  - `policies: {}` so a NON-Codas repo's `policy_registry` stays 0 (no `check_*` symbols
    there);
  - structure has a single repo-root catch-all unit with all `REQUIRED_UNIT_FIELDS`.
- No-clobber: skip an existing file unless `--force`; report written vs skipped.
  Deterministic fixed order.

## Acceptance Criteria

- [x] `codas init` then `codas doctor` on a fresh (temp) repo → doctor healthy (exit 0,
      program/documents optional warns); `codas check` runs (one dogfooding warning,
      exit 0).
- [x] All four templates load through their loaders; no schema errors.
- [x] No-clobber proven (existing files skipped, `--force` overwrites). Deterministic.
- [x] `codas check .` = 0 on this repo; inventory byte-identical; suite green; --verify
      clean (init adds no facts beyond owned app symbols).

## Implemented (2026-06-20) + codex impl review folded

Shipped `app/init.py` + `codas init [--force]`; docs (implementation-plan + design HTML)
updated — init implemented. 310 tests; check 0; byte-identical; --verify clean.

Codex impl review — **APPROVE (0 blockers)**, folded the one SHOULD:
- **Symlink traversal:** a symlinked `.codas/` dir, or a symlinked (even DANGLING)
  target file (`exists()` misreports a dangling link as absent → no-clobber bypass →
  write THROUGH the link to an out-of-repo target), was a hole for a setup tool that may
  run in CI / untrusted repos. Fixed: a symlinked `.codas/` is refused; a symlinked
  target is treated as present (skipped without `--force`) and replaced with a real file
  (link dropped, never followed) under `--force`. Three regression tests added.

## Out of scope

- Scaffolding `program.yml` / `documents.yml` (optional unless declared) or `.trellis/`.
- Interactive prompts / project-name detection. Trellis-native hook wiring (a documented
  recipe in the P6 wrap; non-blocking by Trellis design).
