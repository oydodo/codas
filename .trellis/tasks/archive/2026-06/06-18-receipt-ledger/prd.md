# PRD — P4 C2: receipt ledger

## Context

P4 (`program:P4:preflight-receipts`) exit: "Agent work can prove which
task/inventory/check it used." C1 shipped the provenance hashes (inventory_hash +
policy_version). This slice records them in a durable **Receipt**.

**Receipt** (authoritative, CONTEXT.md): "a durable record of a Codas run or agent
work session, including inputs, inventory version, policies run, findings and check
result." Repo state (§12): receipts live in `.codas/receipts/<timestamp>.json` and
are "usually local or CI artifacts" (gitignored — `.codas/receipts/*.json` already
in `.gitignore`). `Receipt` is a core domain model (plan §3).

## Goal

`codas check --receipt` writes a durable, self-describing receipt of the run —
inputs + the C1 provenance hashes + the findings + the pass/fail result — to
`.codas/receipts/<timestamp>.json`, so a later reader can prove which inventory and
policy config a check used.

## Requirements

1. `core/receipt.py`: `Receipt` frozen dataclass + `to_json()`. Pure (no I/O).
   Fields: `schema_version`, `kind="receipt"`, `timestamp` (ISO-8601 UTC), `repo`,
   `provenance` (`{inventory_hash, policy_version}`), `result`
   (`{ok, error_count, warning_count}`), `findings` (the check's findings JSON).
2. `app/receipt.py`:
   - `build_receipt(repo, report, provenance, now) -> Receipt` — pure assembly from
     a `CheckReport` + provenance + a timestamp (injected for determinism in tests).
   - `write_receipt(repo, report, now=None) -> Path` — computes provenance, builds
     the receipt, writes pretty deterministic JSON to
     `.codas/receipts/<basic-timestamp>.json` (colons stripped for filesystem
     safety, e.g. `2026-06-18T120000Z.json`); creates the dir; returns the path.
3. `cli.py`: `codas check --receipt` writes a receipt after the check and prints its
   path. Default `codas check` is unchanged (no receipt, deterministic).

## Acceptance criteria

- `codas check . --receipt` writes a valid receipt JSON under `.codas/receipts/` and
  prints its path; the receipt's `provenance` equals `compute_provenance(repo)` and
  `result.ok` matches the check.
- `build_receipt` with a fixed `now` is deterministic (byte-identical body across
  two builds); the timestamp/filename is the only run-varying part.
- Receipts are gitignored → they never appear in `discover_files`, so
  `codas check .` stays "No Codas findings" and `codas inventory` is unaffected.
- Full suite green.

## Non-goals

- Writing a receipt on every `codas check` (opt-in `--receipt` only — no surprise
  files; default check stays deterministic).
- A task/work-item field on the receipt — added with the `codas preflight` context
  pack (C3), which knows the task.
- A `waiver_version` in provenance — later facet (carried from C1).
- Receipt querying/rotation/ledger pruning — receipts are append-only files; a
  `codas` reader/rotation command is a later facet.
