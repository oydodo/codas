# Reconcile authoritative docs with P0-P5 reality (defer status to program.yml)

## Goal

A 6-agent parallel audit found ALL authoritative + supporting docs at **major_drift** —
every one predates P3-P5 (dated Jun 17-18). Reconcile them to current reality with
**targeted** edits (depth = option 1), closing the exact dogfood gap the project keeps
hitting: design-level changes (P3 adapter boundary, P4 preflight/receipts, the whole P5
wiki spine, spec_drift, call-graph facts) never propagated to the authoritative design
docs.

## Principle (the load-bearing one)

These docs carry TWO kinds of content:
1. **Phase/deliverable STATUS** — already owned as fact by `.codas/program.yml`. The docs
   DUPLICATE it (e.g. "P5 = future MCP", "P0-P4 complete", "15 policies") → guaranteed to
   re-drift every phase. **Fix: stop duplicating — replace hardcoded status with a pointer
   to `.codas/program.yml` (the living source of truth).** (This is the "anchor prose to
   facts" principle; the same disease as committed generated pages churning.)
2. **Architecture NARRATIVE + DECISIONS** — durable design content. Mostly still valid;
   the drift is MISSING decisions (wiki spine, spec_drift, ScanContext seam, the adapter
   set) and a few outright contradictions. **Fix: correct contradictions + add the
   load-bearing decisions.** Do NOT rewrite the still-valid narrative.

Targeted, not comprehensive (a full rewrite would re-duplicate facts and re-drift).

## Scope — per-doc edit spec

**docs/codas-implementation-plan.html** (authoritative master):
- §8 P5 row: stale (lists ~3 deliverables; 9 shipped). Replace the hardcoded P5
  deliverable list + phase-status with the actual P5 wiki-spine summary AND a note
  "current phase/deliverable status is owned by .codas/program.yml".
- §11 adapter table: add `wiki` (markdown -> wiki_claims), `callgraph` (stdlib-ast
  first-party call facts; pyan rejected for nondeterminism), `git` (diff -> changed_paths
  substrate for spec_drift).
- §6 data contracts: add `source_inventory_hash` (inventory hash excluding
  `.codas/wiki/generated/`; the page narrows it further to its rendered fields).
- §3 system layers: add the ScanContext fact-provider seam (codas.facts.context;
  adapters never imported by core/policies; dependency_direction enforces it).
- §5 module table: wiki module marked P3 -> it shipped in P5 (--emit-pack/--write/--verify).
- §12 repo-state: `.codas/wiki/` add the committed `generated/` subdir.

**docs/codas-design.html** (authoritative product/architecture):
- Header: "Draft for Implementation" / 2026-06-17 -> note it is the design record; phase
  status is in program.yml.
- §21 MVP plan: **CONTRADICTION** — P5 described as "LLM-assisted clustering + MCP".
  Reality: P5 = wiki reconciliation (deterministic, agent-driven, no embedded LLM/MCP);
  MCP -> P7. Add P6 (enforcement) + P7 (MCP + OSS backends) to the roadmap.
- §11.1 policy table: lists 7; 17 are wired. Reconcile (or point to .codas/policies.yml).
- Add the wiki architecture decision (grounds/renders/verifies; atlas:claims;
  generated_wiki_drift) and spec_drift (materiality-as-claim) at a design level, pointing
  to the decision records (06-19-wiki-architecture).

**docs/codas-structure-map-schema.html** (authoritative schema):
- Reconcile to current reality (major_drift). Keep the schema definition (format is
  stable). Clarify `must_update_if_changed` semantics if drifted; note any new field used
  by the inventory; defer status to program.yml. (Auditor flagged major_drift; the editor
  agent re-audits and fixes specifics.)

**README.md** (supporting):
- Status section: "P0-P4 ... 15 policies ... P5 in progress" -> "P0-P5 complete; see
  .codas/program.yml for the living phase/deliverable status" (no hardcoded counts).
- Atlas Wiki section: `generated_wiki_drift` is SHIPPED (not "planned").
- Usage: add `codas wiki --emit-pack | --write | --verify`.

**.codas/wiki/concepts/codas-product.md** (supporting wiki concept):
- "Current Implementation State": "P0 CLI core" -> defer to program.yml + a durable
  one-line capability summary. Keep the rest (durable).

**CONTEXT.md** (domain glossary):
- MINIMAL: add only genuinely DOMAIN concepts new this session — Drift vs Stale
  (change-triggered vs state-based), Grounding / Verification (Codas grounds, an LLM
  renders, Codas verifies). Do NOT add implementation terms (ScanContext, atlas:claims,
  source_inventory_hash) — this is a domain glossary, not an implementation index.

## Dogfood-cleanliness (must hold)

- `codas check .` = 0 after edits. Editing `.md` (README/CONTEXT/codas-product) creates
  `doc_claims`/`wiki_claims` -> any path/link added must EXIST and (for a wiki
  canonical-source) be config-declared. HTML edits create no claims (adapters parse only
  `.md`). No new structure unit; no `must_update_if_changed` gating (spec_drift v1 =
  drift_couplings only, empty).
- `inventory --json` byte-identical (docs are facts; deterministic). Full test suite green
  (no code change). No regeneration of governance.md needed (units/program unchanged).

## Acceptance Criteria

- [ ] All 6 docs reconciled per the spec; hardcoded phase-status replaced with a pointer
      to `.codas/program.yml`.
- [ ] The §21/design.html P5=MCP contradiction and the §8/plan.html stale P5 deliverables
      are corrected; the wiki spine + spec_drift + ScanContext + the 3 new adapters are
      present in the authoritative plan/design.
- [ ] `codas check .` = 0; full suite green; `inventory --json` byte-identical; `codas
      wiki --verify` clean.
- [ ] No new stale_claim/stale_wiki_claim finding from any added link.

## Notes

- Then proceed to the queued tasks (06-19-incremental-fact-cache, 06-19-spec-drift-fact-
  delta) on accurate docs.
- This task itself is the dogfood lesson made concrete: docs that duplicate program.yml's
  facts drift; the reconciliation both fixes the drift AND removes the duplication that
  caused it.
