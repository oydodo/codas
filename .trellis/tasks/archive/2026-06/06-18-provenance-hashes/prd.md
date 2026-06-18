# PRD — P4 C1: provenance hashes

## Context

P4 (`program:P4:preflight-receipts`) exit criterion: "Agent work can prove which
task/inventory/check it used." Deliverables: task context pack, receipt ledger, and
**inventory hash + policy version provenance**. The provenance hashes are the
foundation the receipt (C2) and preflight pack (C3) reference. This slice ships them.

Definitions (authoritative): a **Receipt** is "a durable record of a Codas run or
agent work session, including inputs, **inventory version**, **policies run**,
findings and check result" (CONTEXT.md). The "inventory version" and "policies run"
are exactly the two hashes here.

## Goal

Deterministic content hashes that pin (a) the inventory facts a run observed and
(b) the policy configuration it ran, surfaced on `codas check --json` so any run is
provable and diffable.

## Requirements

1. `core/provenance.py`:
   - `inventory_hash(repo) -> str` — `sha256:` of the canonical inventory JSON (the
     existing byte-identical `codas inventory` output). Hashing the *output* (the
     contract), not internals.
   - `policy_version(repo) -> str` — `sha256:` of the canonical-serialized
     `policies.yml` mapping (severities + options — what defines "which check").
   - `compute_provenance(repo) -> dict` — `{"inventory_hash", "policy_version"}`,
     deterministic, sorted.
   - Format `"sha256:<hex>"`; pure stdlib `hashlib`/`json`.
2. `codas check --json` output gains a top-level `provenance` block
   `{inventory_hash, policy_version}`. (The human `codas check` and the
   deterministic `codas inventory` output are unchanged.)

## Acceptance criteria

- `compute_provenance` is byte-stable across two runs (same repo → same hashes).
- Changing a tracked fact (e.g. adding a symbol) changes `inventory_hash`;
  changing a policy severity in `policies.yml` changes `policy_version`; the two are
  independent.
- `codas check . --json` includes `provenance.inventory_hash` /
  `provenance.policy_version` matching `compute_provenance`.
- `PYTHONPATH=src python3 -m codas check .` → "No Codas findings" (provenance is
  metadata, never a finding); `codas inventory . --json` byte-identical across runs.
- Full suite green.

## Non-goals

- The **Receipt** model + `.codas/receipts/` ledger writer — C2 (consumes these
  hashes).
- The **Context Pack** / `codas preflight` command — C3.
- A timestamp/run-id (those belong on the receipt, C2; provenance hashes are
  content-addressed and timestamp-free to stay deterministic).
- Hashing the policy *code* / git SHA — `policy_version` pins the declared policy
  config, not the engine version (engine-version provenance is a later facet).
- A standalone `codas provenance` command — provenance is surfaced via `check`
  (and later the receipt), not a new top-level app service.
