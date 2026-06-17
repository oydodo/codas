# P0 Codas CLI Core Self-Check

## Problem

Codas has a formal design and implementation plan, but the executable code is
still incomplete. The next implementation slice must create a real `codas` CLI
and make Codas start checking its own repo-local configuration and Trellis task
facts.

## Goal

Implement the smallest useful Codas core/self-check path. The legacy
`harness_guard` prototype is removed rather than preserved as a compatibility
layer.

## Requirements

- Add a `codas` Python package with CLI entrypoint.
- Add a `codas` console script and `scripts/codas` wrapper.
- Remove the legacy `harness_guard` package and `scripts/harness-guard`.
- Load `.codas/config.yml`, `.codas/policies.yml` and `.codas/waivers.yml`.
- Validate configured authoritative/supporting source globs.
- Validate dogfooding protocol HTML fragment target.
- Validate Trellis task globs include and resolve `task.json`, `prd.md`,
  `implement.jsonl` and `check.jsonl` where applicable.
- Emit evidence-backed findings in text and JSON formats.
- Add tests for config loading and Codas self-check behavior.

## Non-Goals

- Do not implement full wiki generation.
- Do not implement MCP.
- Do not install hooks.
- Do not fully rewrite Swift/Ciri prototype checks in this slice.

## Acceptance Criteria

- `PYTHONPATH=src python3 -m codas check .` runs.
- `PYTHONPATH=src python3 -m codas check . --json` emits machine-readable output.
- `python3 scripts/codas check .` runs.
- Unit tests pass.
- Trellis task context validates.
