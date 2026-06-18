# P1 doc claim index, task facts and trellis_context realign

## Goal

Close out the P1 remaining deliverables: a **doc claim index** (Markdown adapter
extracting path references from docs) and **Trellis task facts** (Trellis adapter
reading task records), both surfaced in `codas inventory`; and **realign the
`trellis_context` policy** to Trellis 0.6.2's task model (implement/check.jsonl
are conditional, not mandatory).

## Authoritative sources

- `docs/codas-implementation-plan.html` — §5 module design (Markdown Adapter and
  Trellis Adapter are MVP/P1; "Extract path references and structured claims from
  Markdown-like docs" → claim facts, stale path candidates; "Read tasks, current
  task, archived tasks, PRDs and context JSONL" → workflow facts, task claims),
  §6 Fact/Claim contracts, §10 policy roadmap (`stale_claim`: markdown path
  references point to existing files — the consuming policy is P2).
- Trellis 0.6.2: `init-context` removed in v0.5.0-beta.12; implement.jsonl /
  check.jsonl are seeded conditionally and curated during planning. PRD-only
  lightweight tasks are valid (`task.py create` output says so).

## Scope (this task)

1. **Markdown adapter / doc claim index** (`src/codas/adapters/markdown.py`):
   scan the repo's Markdown files (`*.md`) for repo-relative path references —
   markdown link targets `[..](target)` and backtick code spans that look like
   paths. Emit deterministic doc-claim facts: `{source, line, path, exists}`.
   No HTTP/anchor/external refs. This is fact extraction only; the `stale_claim`
   policy that consumes it is P2 (out of scope).
2. **Trellis adapter / task facts** (`src/codas/adapters/trellis.py`): read
   `task.json` across active and archived tasks (config `workflow_task_globs` /
   `<root>/tasks/**/task.json`); emit `{id, status, package, dev_type, priority,
   archived}` task facts, deterministic.
3. **Inventory**: add deterministic `doc_claims` and `tasks` sibling blocks to
   the `codas inventory` JSON (flat §5 keys untouched).
4. **Realign `trellis_context`**: `REQUIRED_TASK_FILES` → `task.json`, `prd.md`
   only (implement.jsonl / check.jsonl are optional in 0.6.2). Update the message
   / recommendation to drop the removed `init-context` flow.
5. **Register**: new `codas-adapters` unit (`src/codas/adapters`) in
   `structure.yml` (active, owner Codas Core), in `codas-source.allowed_children`.
6. **Tests**: markdown path extraction (link + backtick, exists flag, ignores
   http/anchors), trellis task facts (active + archived, status), inventory
   blocks present + deterministic, trellis_context (missing jsonl no longer
   warns; missing prd.md still warns).

## Non-Goals (defer)

- The `stale_claim` policy (P2) and any finding from doc claims — index only.
- P2 substantive structure policies.
- Structured/semantic claim parsing beyond path references.
- No LLM similarity (plan §17).

## Acceptance Criteria

- [ ] `src/codas/adapters/` exists (markdown + trellis), registered active in
      `structure.yml`.
- [ ] `codas inventory . --json` includes deterministic `doc_claims` and `tasks`
      blocks; re-running yields byte-identical output.
- [ ] `trellis_context` no longer warns on a task missing implement/check.jsonl;
      a task missing `prd.md` still warns.
- [ ] `codas check .` passes (exit 0, 0 errors); bootstrap gate clean.
- [ ] New unit tests pass.

## Notes

- Affected concepts: **Fact**, **Claim**, **Evidence**, **Atlas Inventory**,
  **Trellis Task System**.
- Markdown extraction is conservative and deterministic — it is signal for P2's
  `stale_claim`, not a policy itself; emit `exists` per reference.
