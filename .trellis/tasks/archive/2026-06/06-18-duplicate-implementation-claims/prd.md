# PRD: Duplicate implementation policy with relationship claims

## Context

High-value P2 gap: promote duplicate detection from the warning-only
`duplicate_symbol` first cut to the schema §8 / plan §10 enforcement, and
introduce the first-class **Claim** concept (§6 Fact/Claim/Finding) that Codas has
not yet had — only Facts (inventory) and Findings (policies) exist so far.

Authority:
- `docs/codas-structure-map-schema.html` §8 — `duplicate_implementation`: "Error
  when a second implementation lacks a declared relationship."
- `docs/codas-implementation-plan.html` §10 — `duplicate_implementation` First:
  "Repeated symbols or concepts require canonical, variant or migration claims."
  §6 — Claim is a core domain object. §17 — no LLM.

This has real teeth on this repo: four genuine private duplicate helpers exist —
`_rel` (×5), `_mapping` (×4), `_optional_str` (×3), `_str_tuple` (×3) — which the
shipped `duplicate_symbol` (public-only, warning) deliberately hides. This policy
detects them (public + private) and requires each to carry a declared
canonical / variant / migration **relationship claim**, or it errors.

## Goals

1. A minimal **Claim surface** `.codas/claims.yml` (`duplicate_relationships`):
   each entry declares a symbol name, a `relationship ∈ {canonical, variant,
   migration}`, an `owner`, and a `reason`. Loaded by a small loader (mirrors the
   waivers loader); registered as a governed, authoritative artifact.
2. `duplicate_implementation` (severity: error): detects top-level symbol names
   (public AND private) defined in ≥2 `src/` modules; suppresses any name with a
   matching relationship claim; emits an error Finding for each unclaimed
   duplicate, with every defining module+line+kind as evidence.
3. This policy **coexists** with `duplicate_symbol` (revised per codex review —
   plan §10 lists both as distinct policies): `duplicate_symbol` stays the
   public-name warning detection signal; `duplicate_implementation` is the
   claim-aware error enforcement over public + private symbols. Both wired, both
   declared. The Python symbol adapter and inventory `symbols` facts are unchanged.
4. Declare the four real repo duplicates in `.codas/claims.yml` as `variant`
   relationships (intentional local private helpers) so `codas check .` returns to
   0 via explicit governance — the duplicates are now declared and checkable, not
   silently ignored.
5. Wired into `codas check .`; covered by tests; inventory unchanged
   (byte-identical across runs).

## Non-Goals (deferred)

- **Concept-level / semantic** duplicate detection (`duplicate_concept`, LLM) —
  §17 forbids LLM for P2; later.
- **Module-set-aware claim matching** (a claim scoped to an exact module set).
  First cut matches by symbol name only; note as later.
- **Cross-language** symbols; **signature / overload** awareness.
- **Migration windows / expiry** on relationship claims (waiver-style).
- **Configurable source scope** beyond `src/` (carried over from the prior slice).

## Acceptance Criteria

- A top-level name (public or private) in ≥2 `src/` modules with NO relationship
  claim → one error Finding, check_id `duplicate-implementation`, evidence per
  defining module (path+line+kind), deterministically ordered.
- A name with a matching `duplicate_relationships` claim → no finding.
- `.codas/claims.yml` parses via the loader; a malformed claim set yields a single
  load-error finding (mirrors policies/waivers load errors).
- The four real repo duplicates are declared and therefore suppressed →
  `codas check .` stays at 0 findings.
- `duplicate_symbol` is fully removed; no dangling references; tests updated.
- Deterministic; `PYTHONPATH=src python3 -m unittest discover -s tests` passes.
- Dogfooding: `.codas/claims.yml` registered in `.codas/structure.yml` (new unit)
  and `.codas/config.yml` authoritative sources; new policy + loader files
  governed; `inventory.unowned` stays empty.
