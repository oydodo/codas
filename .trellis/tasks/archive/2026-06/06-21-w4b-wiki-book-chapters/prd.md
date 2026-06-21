# W4b: render remaining wiki/ book chapters (all code units)

## Goal

Generalize the W4a book renderer from one hardcoded chapter (`codas-app`) to a chapter for
EVERY code subsystem. The renderer already loops a chapter set; W4b makes that set DERIVED
(every unit that owns ≥1 knowledge-tree node) instead of a static `("codas-app",)` tuple.

## Scope / decision

- **Chapter set = DERIVED, not hardcoded**: render a chapter for each Structure-Map unit that
  owns ≥1 node in the (product-scoped) knowledge tree. Measured today = 10 units:
  codas-adapters, codas-app, codas-config-loader, codas-core-models, codas-facts,
  codas-policies, codas-reporting, codas-source, codas-structure-module, role-integrations.
  This auto-includes the right set and auto-excludes empty / non-code / not-on-disk units —
  the actual generalization, not a longer literal list.
- **Non-code units stay index entries** (program-plan, agents-guide, claim-set, codas-docs,
  trellis-workflow, …): they own no symbols, so a module→symbol tree-slice + dependency
  mermaid is the wrong shape. They remain listed in the index (plain, no chapter, no dead
  link). Doc/config chapter TYPES are a deliberate future enhancement, NOT W4b.
- **No gate-semantics change**: pure app-layer rendering (no scanner change, no policy, no
  fact_coupling). DESIGN review not required; codex IMPL review still run. `wiki/` stays
  scanner-excluded; `--verify` byte-compares all chapters; orphan detection unchanged.

## Requirements

- R1 — `project_book` derives the chapter set from tree-node ownership (sorted, deterministic).
- R2 — one `wiki/<unit_id>.md` per code unit; same chapter shape as W4a (heading + owner +
  tree-slice + dependency mermaid + one open-world banner).
- R3 — index links every rendered chapter, lists non-code units plain (no dead links).
- R4 — determinism: `--write` idempotent, `--verify` clean; byte-identical inventory preserved.

## Acceptance Criteria

- [ ] `codas wiki --write` renders 10 chapters + index; `--verify` clean after write.
- [ ] A non-code unit (e.g. `program-plan`) has NO chapter file and NO index link.
- [ ] A code unit beyond codas-app (e.g. `codas-policies`, `codas-facts`) renders with its
      tree-slice + mermaid + open-world banner.
- [ ] `codas check` == 0; inventory byte-identical 2×; full suite green.
- [ ] New tests: derived set covers the 10 code units, excludes non-code; multi-chapter render.

## Notes

- W5 unify / W6 prose / W7 register+CONTRACT+existence-fix / W8 packaging follow (program.yml P8).
- The latent claim-existence leak (W4a, deferred to W7) is unchanged here — still inert,
  still guarded by `LatentLeakGuardTests`.
