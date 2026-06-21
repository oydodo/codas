# Opinionated canonical repo layout + scaffolding — Codas manages repo structure

## Status: BACKLOG / DEFERRED (big task — do NOT work now)

Placed as a tracked backlog item (2026-06-21). Same onboarding bucket as W8 packaging +
cross-repo scaffolding. Revisit after the injection MVP + W8.

## Goal

Make Codas opinionated about repo STRUCTURE, not just per-file ownership — so a new repo gets a
canonical layout out of the box and "Codas manages the repo structure" becomes real onboarding,
not just a per-file `missing_owner` check.

## Sketch (not a committed design)

- `codas init` scaffolds a canonical layout (e.g. `src/` product, `.codas/` meta, `docs/`,
  `wiki/` book) + sets `workspace.roots` to those (tighter than `["."]`) + seeds
  `structure.yml` with canonical units + `canonical_placement`.
- A new policy: **product code outside the canonical roots = finding** — this CLOSES the
  governance hole a tight whitelist would otherwise open (you can tighten scope AND still catch
  code slipped outside the canonical dirs). This is the piece that makes a whitelist safe.
- Distinct from `06-21-scope-exclude-knob` (that = the exclude LEVER / hash-scope decoupling;
  this = an opinionated DEFAULT layout + scaffolding + the outside-canonical policy).
- `structure.yml` ALREADY manages structure (units / owner / canonical_placement /
  deprecated_paths); this layers an opinionated default + scaffolding + onboarding on top.

## Open questions (for when it's picked up)

- How opinionated? A single canonical layout vs a few presets (lib-layout, src-layout, monorepo).
- Does tightening default roots break the default-govern safety property? (The outside-canonical
  policy is what makes it safe — design it together.)
- Interaction with `wiki.product_roots` (already config-driven) + the scope-exclude knob.
- Migration: how an EXISTING repo adopts the canonical layout without churn.

## Notes

- Big, gate-adjacent (new policy + scan-scope defaults) -> codex DESIGN review when picked up.
- DO NOT start without an explicit decision to take it off the backlog.
</content>
