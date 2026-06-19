# P5 D3d generated_wiki_drift policy (verify atlas:claims vs facts)

## Goal

The "VERIFY" half of the wiki spine: a `generated_wiki_drift` policy that parses the
`atlas:claims` block of each committed generated page and verifies its claims against
repository facts. A generated page asserting something the facts contradict (a
hallucinated/false claim) is an **error** — this is the §17 guardrail that lets the LLM
generation path stay honest (any unverified claim a host agent writes into a generated
page is caught deterministically). Implements design `06-19-wiki-architecture` §3 link
③/④ + §4 `generated_wiki_drift`.

## Why a NEW parser (not the wiki adapter)

The existing `extract_wiki_claims` is fence-aware and SKIPS fenced content — so it does
NOT parse the `atlas:claims` fenced block (that is exactly what makes the generated page
dogfood-clean for `stale_wiki_claim`). D3d therefore needs its own parser that reads
INSIDE the `atlas:claims` fence. New adapter extractor + ScanContext accessor (§11); the
policy consumes facts, never parses.

## Scope (D3d)

- `adapters/wiki.py`: `extract_generated_claims(repo, files, generated_root) ->
  GeneratedClaims` — parse the `atlas:claims` block of each `.md` under
  `.codas/wiki/generated/`. Returns per-page `{source, source_inventory_hash, claims,
  has_block}` where each claim is `{source, line, kind (unit|roadmap), subject, value}`.
- `ScanContext.generated_claims()` memoized accessor.
- `policies/generated_wiki_drift.py::check_generated_wiki_drift(ctx)`:
  - **structural (link ③)**: a generated page must carry a nonempty `atlas:claims`
    block with a `source_inventory_hash` line and ≥1 claim — else **error**.
  - **fact-consistency (link ④)**: each `unit: <id> -> <path>` claim must match a
    Structure Map unit (`id` exists with that `path`); each `roadmap: <id> -> <status>`
    must match a Program Plan work item (`id` exists with that `status`). A mismatch or
    unknown subject is an **error** (a verifiable lie blocks).
  - Severity `error`. Deterministic (total-key sort). Consumes facts via ScanContext +
    `load_structure_map`/`load_program_plan` (no adapter import in the policy).
- Wire `check_generated_wiki_drift(ctx)` into `run_check`; declare in `policies.yml`;
  add to the orchestration one-ctx-forwarded test.

## Freshness is NOT in check (deferred to D3c `--verify`)

Design §4 lists a `source_inventory_hash`-freshness **warning**. But the committed
page's hash goes stale on *every* `src/` commit, and the dogfood bar is `check . = 0`
**including warnings** — so a freshness warning in `check` would break the gate on every
unrelated commit. Resolution: `check` verifies the **claims** (a wrong `unit:`/`roadmap:`
claim = error — the *meaningful* drift signal, which forces regeneration when units/
program actually change); the cosmetic `source_inventory_hash` comparison is surfaced by
the opt-in `codas wiki --verify` (D3c) / CI, not the always-on gate. The policy still
*requires the hash to be present* (link ③), it just does not compare its value in check.

## Dogfood-cleanliness (must hold)

- The committed `.codas/wiki/generated/governance.md` claims (`unit:`/`roadmap:`) match
  current Structure Map units + Program Plan statuses (the page was generated from
  them; they are unchanged) → `generated_wiki_drift` = 0 on the real repo. No page
  regeneration needed for this slice (claims still accurate; only the hash is stale, and
  the hash value is not checked in `check`).
- New top-level names unique across `src/` (no `duplicate_implementation`).

## Acceptance Criteria

- [ ] `extract_generated_claims` parses `source_inventory_hash` + `unit:`/`roadmap:`
      lines from the `atlas:claims` fence; ignores other fences/prose; deterministic.
- [ ] Golden fixture: a generated page with a bogus `unit: x -> wrongpath` →
      `generated-wiki-drift` **error**.
- [ ] Golden fixture: a page missing the `atlas:claims` block (or empty / no
      `source_inventory_hash`) → **error**.
- [ ] A correct generated page → 0 findings.
- [ ] `roadmap:` mismatch (wrong status / unknown id) → error.
- [ ] Real repo: `codas check .` = 0 (committed governance.md verifies clean).
- [ ] `inventory --json` byte-identical (generated_claims is a policy-time fact, NOT in
      inventory — like changed_paths/spec_drift; do not serialize it).
- [ ] Orchestration one-ctx test patched for the new ctx consumer; full suite green.

## Notes

- This is the deterministic enforcement that makes "Codas grounds it, an LLM renders it,
  Codas verifies it" real: the host agent may write a generated page, but a claim the
  facts don't support is an error finding.
- `source_inventory_hash` value-comparison (freshness) + render-vs-ondisk drift = D3c
  `codas wiki --verify`. CONTRACT.md + AGENTS.md pointer = D3e. Regenerate governance.md
  at D3c (it is stale-by-source).
