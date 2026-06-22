# Decouple preflight digest from Trellis relatedFiles (git-derived affected files)

## Goal

Remove the `related_files` coupling. The injection MVP made Codas read Trellis's `task.json`
`relatedFiles` field to drive the preflight digest. That was three mistakes at once:
- **adapter-agnostic violation** — bound a core capability to one workflow adapter's private schema;
- **layer violation** — "what code a task touches" is a CODE fact, not workflow metadata;
- **declaration not fact** — a hand-filled field (forgotten/stale), against Codas's open-world core.

The digest now derives affected code from the git WORKING-TREE diff — Codas's own fact source —
so it lights up for whatever code the agent is currently touching, no declaration needed.

## Requirements

- R1 — Remove `related_files` everywhere: `adapters/trellis.py::TaskFact` field + `_path_list`,
  `structure/inventory.py` task row. Codas reads ZERO Trellis code-relationship fields.
- R2 — `preflight._build_digest` derives affected paths from `ScanContext.changed_paths()` (the
  git working-tree diff via `adapters/git.extract_changed_paths`), reached through the facts seam
  (`build_scan_context`) — §11-clean (codas-app → codas-facts, never an adapter import).
- R3 — One `ScanContext` built and reused for the inventory (no second scan); pack determinism +
  provenance unchanged.
- R4 — Reuse candidates scoped to `wiki.product_roots` so touching tests / `.trellis` scripts
  never floods the digest with non-product symbols. Affected units stay honest (all touched).
- R5 — Digest stays pack-only (never in the inventory hash) + advisory (§17), so git volatility
  is fine. check 0; inventory byte-identical 2x; verify clean; suite green.

## Acceptance Criteria

- [x] `related_files` gone from adapter + inventory; Codas reads no Trellis relatedFiles.
- [x] digest populates from the working-tree diff (live-proven on this repo) + product-scoped
      reuse (645 → 215 candidates once `.trellis` scripts excluded); empty on a clean tree.
- [x] check 0; byte-identical 2x; wiki/agents --verify clean; 519 tests.

## Notes

- Not gate-semantics (digest is advisory/pack-only; no policy/scan/hash-scope change) → no codex
  DESIGN review required. codex MCP is unusable; risk areas self-verified (§11 via dependency_
  direction = 0, determinism via byte-identical, provenance via the suite's provenance-match test).
- `relatedFiles` stays in Trellis (Trellis's field); Codas simply no longer reaches into it.
- Future option (NOT built): an intent-ahead-of-edit override via a Codas-owned channel (e.g.
  `preflight --touches a.py,b.py`), never a workflow adapter field. branch-vs-base (persist across
  commits within a task) also deferred — working-tree diff covers active editing.
