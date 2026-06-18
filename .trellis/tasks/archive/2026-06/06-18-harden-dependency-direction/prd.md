# PRD — P3 review follow-up: harden dependency-direction

## Context

The holistic codex review of the merged P3 phase raised two non-blocking items on
the dogfooded adapter-boundary enforcement (`dependency_direction` policy + the
`structure.yml` `dependency_rules`):

- **(nit) Duplicate findings.** `from codas.adapters import python` emits two import
  facts (the package `codas.adapters` + the submodule `codas.adapters.python`), so
  the policy reports the *same* boundary violation twice for one import statement.
- **(should) Narrow rule.** Only `codas-policies must_not_depend_on codas-adapters`
  is declared, so the §11 boundary is enforced for the policy layer only. Other core
  units that legitimately must not touch adapters (app, core models, reporting,
  config) are unguarded — a future import from them into an adapter would not be
  caught.

Confirmed: only `codas.facts.context` (the seam) and `codas.structure.inventory`
(the legit adapter→facts bridge) import adapters today; all other src/codas units
are adapter-free.

## Goal

One finding per `(importer file, forbidden unit)`, and the boundary rule covers
every core unit except the seam and the bridge.

## Requirements

1. `dependency_direction`: dedup violations to one finding per
   `(importer_module, forbidden_unit)`, keeping the most-specific (longest
   `target_path`) offending edge as evidence.
2. `structure.yml` `dependency_rules`: add `must_not_depend_on: [codas-adapters]`
   to `codas-app`, `codas-core-models`, `codas-reporting`, `codas-config-loader`
   (NOT `codas-facts` — the seam — nor `codas-structure-module` — the bridge).

## Acceptance criteria

- A single `from pkg.adapters import sub` style import yields exactly one
  dependency-direction finding (regression test).
- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings" (all newly-guarded
  units are adapter-free today).
- `codas inventory . --json` byte-identical across two runs; full suite green.

## Non-goals

- Unifying `build_inventory` with `ScanContext` (P3 review should #1) — separate
  deferred debt.
- Relocating adapter fact-types to a neutral module (review should #3) — separate.
- `may_depend_on` allow-list enforcement — later facet.
