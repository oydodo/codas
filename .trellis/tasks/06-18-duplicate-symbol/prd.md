# PRD: Duplicate symbol policy

## Context

Final substantive P2 policy slice. Consumes the Python symbol facts shipped last
slice (`adapters/python.py` → inventory `symbols.definitions`) to flag repeated
public type/function names across governed source modules — the deterministic,
language-adapter-level first cut of duplicate detection.

Authority:
- `docs/codas-implementation-plan.html` §10 — `duplicate_symbol` First
  Implementation: "Language adapters emit repeated type/function names." Later:
  "Concept-level semantic duplicate detection." `duplicate_implementation` First:
  "Repeated symbols or concepts require canonical, variant or migration claims."
- `docs/codas-structure-map-schema.html` §8 — `duplicate_implementation`: "Error
  when a second implementation lacks a declared relationship."
- §17 — no LLM for P2 correctness.

Naming: the repo's `.codas/policies.yml` declares `duplicate_concept` (matching
`docs/codas-design.html`) — the concept-level / semantic variant, which needs LLM
similarity and is a documented later expansion. The deterministic policy built
here is the distinct `duplicate_symbol` from plan §10. This slice ADDS a
`duplicate_symbol` declaration to `.codas/policies.yml` and leaves
`duplicate_concept` as the later semantic policy.

## Scope decision (dogfood-driven)

Probe of this repo's `symbols.definitions`: the only names repeated across
modules are leading-underscore private helpers (`_rel` ×5, `_mapping` ×4,
`_optional_str` ×3, `_str_tuple` ×3) — intentional local encapsulation, not
duplicate implementations of a capability. So the policy scopes to:
- **public** symbols only (name not starting with `_`), and
- modules under **`src/`** (implementation source; excludes `tests/` test
  helpers and vendored `.trellis/scripts`).

With that scope there are zero duplicates on this repo → `codas check .` stays at
0. The policy is the regression guard against a genuine second public
implementation of the same name; firing is proven by fixtures.

## Goals

1. `duplicate_symbol` (severity: warning): for each public top-level symbol name
   defined in ≥2 distinct `src/` modules, emit one warning Finding listing every
   defining module + line, recommending consolidation / a declared
   canonical-variant-migration relationship / a waiver.
2. Add the `duplicate_symbol` declaration to `.codas/policies.yml`.
3. Wired into `codas check .`; covered by tests.
4. Dogfooding invariant preserved: `codas check .` stays at 0 findings.
5. `codas inventory` stays byte-identical across two runs (unchanged — the policy
   adds no inventory fields).

## Non-Goals (deferred)

- **`duplicate_implementation` claim mechanism** — declaring a symbol pair as
  canonical/variant/migration to suppress a finding. No claim store exists yet;
  the waiver system is the interim escape hatch. Error-severity, claim-aware
  duplicate_implementation is later.
- **Concept-level / semantic duplicate detection** (`duplicate_concept`) — needs
  LLM similarity; §17 forbids it for P2 correctness. Later.
- **Private / nested / method-level symbols**, cross-language symbols, and
  signature-aware overload handling.
- **Configurable source scope** — `src/` is hardcoded for the first cut.

## Acceptance Criteria

- A public name defined in 2+ `src/` modules → exactly one warning Finding,
  check_id `duplicate-symbol`, evidence = one entry per defining module (path +
  line), deterministically ordered.
- Private (`_`-prefixed) duplicates, single-definition symbols, and duplicates
  confined to `tests/` or `.trellis/` are NOT flagged.
- Deterministic: findings sorted by symbol name; evidence sorted by (module, line).
- `codas check .` → still 0 findings; `PYTHONPATH=src python3 -m unittest
  discover -s tests` passes (new tests added).
- Dogfooding: new policy file under `codas-policies`, new test under
  `codas-tests`; `.codas/policies.yml` gains the `duplicate_symbol` claim.
