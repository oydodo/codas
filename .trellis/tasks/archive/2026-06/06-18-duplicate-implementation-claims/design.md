# Design: Duplicate implementation policy with relationship claims

## Claim surface: `.codas/claims.yml`

First-class §6 Claim surface (Codas has had Facts + Findings but no Claim until
now). Minimal shape:
```
version: 1
kind: claim_set
duplicate_relationships:
  - symbol: _rel
    relationship: variant        # canonical | variant | migration
    owner: Codas Core
    reason: Small private path-relativize helper kept local per module to avoid a shared-utility coupling; intentionally duplicated.
  - symbol: _mapping
    relationship: variant
    owner: Codas Core
    reason: ...
  - symbol: _optional_str
    relationship: variant
    owner: Codas Core
    reason: ...
  - symbol: _str_tuple
    relationship: variant
    owner: Codas Core
    reason: ...
```

Loader: `load_claims(path)` in `config/loader.py` = thin wrapper over
`load_yaml_mapping` (mirrors `load_waivers` / `load_policies`). No new parsing —
PyYAML dup-key rejection still applies.

`VALID_RELATIONSHIPS = {"canonical", "variant", "migration"}` (per §10).

## Policy: `duplicate_implementation` (`src/codas/policies/duplicate_implementation.py`)

Signature: `check_duplicate_implementation(repo, config) -> list[Finding]`

1. Load claims: `claims_path = repo/.codas/claims.yml`. If absent → empty claim
   set (every dup then errors). On `ConfigLoadError` → one `claims-load-error`
   finding, return early (mirrors the waiver load-error pattern).
2. Validate + collect claimed names:
   - `duplicate_relationships` must be a list (else `claim-schema-invalid` error).
   - each entry must be a mapping with non-empty `symbol`, `owner`, `reason`, and
     `relationship ∈ VALID_RELATIONSHIPS`; otherwise a `claim-schema-invalid`
     error finding (indexed, like waivers). Valid entries contribute
     `claimed.add(entry["symbol"])`.
3. Detect duplicates: `extract_symbol_facts` over `discover_files`, group
   top-level symbols (public AND private) under `src/` by name; a name in ≥2
   distinct modules is a duplicate.
4. For each duplicate name NOT in `claimed`, emit:
   ```
   Finding(severity="error", check_id="duplicate-implementation",
       message=f"Symbol '{name}' is implemented in {n} modules without a declared relationship: {mods}",
       evidence=[Evidence(module, line, detail=kind) per occ, sorted by (module,line)],
       recommendation="Consolidate, or declare a canonical/variant/migration relationship in .codas/claims.yml.",
       meta={"name": name, "modules": mods})
   ```
5. Findings sorted by name; schema/load errors sorted ahead deterministically.

Severity = error (schema §8 "Error when a second implementation lacks a declared
relationship"). The claim store IS the suppression mechanism that makes error
appropriate now (the prior warning-only cut existed only because no claim store
did).

Scope = public + private under `src/`: a declared duplicate is a duplicate
regardless of visibility; the four real repo dups are private. `src/`-only keeps
`tests/` helpers and vendored `.trellis` out (carried from the prior slice;
configurable scope still deferred).

## Coexist with `duplicate_symbol` (revised per codex design review #4)

Original plan was to SUPERSEDE `duplicate_symbol`. Codex review correctly noted
that plan §10 lists `duplicate_symbol` and `duplicate_implementation` as DISTINCT
policy rows, and the authoritative plan is unchanged — "avoids double-report" is
not sufficient to remove a plan-declared policy. So both COEXIST:
- `duplicate_symbol` (warning): public-name detection signal (unchanged).
- `duplicate_implementation` (error): claim-aware enforcement over public+private.
On this repo there is no overlap: the four real duplicates are private (invisible
to public-only `duplicate_symbol`) and are claimed (suppressed in
`duplicate_implementation`), so both report 0. The only theoretical overlap is a
future unclaimed PUBLIC duplicate (warning + error) — acceptable and plan-faithful.
Both wired in `check.py`; both declared in `policies.yml`; both dogfood-asserted.

## policies.yml

Replace the `duplicate_symbol` entry with:
```
  duplicate_implementation:
    severity: error
    description: A top-level symbol implemented in two or more src modules must declare a canonical, variant or migration relationship in .codas/claims.yml; otherwise it is flagged as an undeclared duplicate implementation. Concept-level semantic detection is later.
```
`duplicate_concept` stays (the later semantic policy).

## Declare the four real duplicates

`.codas/claims.yml` declares `_rel`, `_mapping`, `_optional_str`, `_str_tuple` as
`variant` (intentional independent private helpers). This returns `codas check .`
to 0 — now via explicit, checkable governance rather than a public-only blind
spot. This is the dogfooding payoff: the repo's real duplication is surfaced and
declared.

## Registration (dogfooding)

- `.codas/structure.yml`: add unit `claim-set` (path `.codas/claims.yml`, kind
  `claim_set`, owner Policy Maintainer) and list it under `codas-config`
  `allowed_children`. (`.codas/claims.yml` is already prefix-owned by
  `codas-config`; the dedicated unit makes the claim surface explicit, matching
  `structure-map` / `program-plan` / `document-manifest`.)
- `.codas/config.yml`: add `.codas/claims.yml` to `constraint_sources.authoritative`.
- These edits keep `config_sources`, `structure_map_loads`, `missing_owner`,
  `structure_drift` all at 0 (the file exists, the unit path exists).

## check.py wiring

Replace `check_duplicate_symbol` with `check_duplicate_implementation` in
`run_check`.

## Determinism

`extract_symbol_facts` sorted; claimed set membership; findings sorted by name;
evidence by (module, line); schema-error findings indexed deterministically. No
timestamps. Inventory untouched → byte-identical.

## Tests

`tests/test_duplicate_implementation_policy.py`:
- two src modules define public `handle` / private `_helper`, NO claim → error
  finding each (public and private both flagged).
- a declared `variant` claim for `_helper` → that name suppressed; unclaimed one
  still errors.
- single-module symbol → no finding; tests/ + `.trellis` dups → no finding.
- malformed `duplicate_relationships` (not a list; entry missing relationship;
  bad relationship value) → `claim-schema-invalid` error.
- missing claims.yml → dups still error (no suppression), no crash.
- determinism: findings sorted by name.

`tests/test_codas_check.py`: swap the `duplicate-symbol` dogfood assertion for
`duplicate-implementation` absent (with the four claims declared, it is 0).

Remove `tests/test_duplicate_symbol_policy.py`.

A loader test in an existing config-loader test module for `load_claims` (parses;
rejects dup keys) if a natural home exists; otherwise fold into the policy tests.

## Dogfooding checklist

- New concepts: first-class **Claim** surface (`.codas/claims.yml`) and the
  `duplicate_implementation` policy. Claim sources updated: policies.yml (policy
  declaration), structure.yml (claim-set unit), config.yml (authoritative source).
- `duplicate_symbol` removed cleanly (no dangling refs).
- New artifacts governed: policy + loader changes under existing units;
  `.codas/claims.yml` under `codas-config` (+ explicit `claim-set` unit).
  `inventory.unowned` stays empty.
- No plan/schema HTML edit (realizes the already-authoritative §6/§8/§10 rows).
- Bootstrap gate: `unittest discover` + `git status --short` clean.
- Link `program:P2:policy-engine-structure-drift` → this task.

## Folded from codex design review

- #1 `_invalid` collision: the policy's own schema-error helper duplicated
  `waivers.py:_invalid` → caught by the policy itself on `codas check .`. Renamed
  to `_schema_invalid`. (The policy proving its worth on its own author.)
- #2 invalid claims must not suppress: `claimed` is now populated ONLY for fully
  valid entries (`_entry_problem` gates it); a malformed entry yields a schema
  finding and contributes nothing.
- #3 name-only matching too loose: claims are now MODULE-SET-AWARE. Each entry
  lists the exact `modules` it covers; a duplicate is suppressed only when the
  observed module set equals a claimed set, so a future copy in a new module is
  NOT silently suppressed (it errors, prompting a claim update).
- #4 coexist (above), not supersede.
- #5 program link: `06-18-duplicate-implementation-claims` added to P2
  `trellis_tasks` alongside the prerequisite `06-18-duplicate-symbol`.
- #6 document governance: `.codas/claims.yml` registered as a `claim_set` document
  role in `documents.yml` (governance-state files are all document roles). Kept
  OPTIONAL (not in `required_roles` / `CANONICAL_REQUIRED_ROLES`): a repo with no
  duplicates needs no claims file, unlike always-present waivers.
- #7 variant-vs-canonical (nit): kept `variant` with reasons that state the
  intentional-locality stance ("kept local to avoid coupling"), an honest
  intentional-variant justification rather than ratifying an oversight.

## Deferred (noted)

Relationship expiry / migration windows, a dedicated `claim-drift` finding (vs the
generic duplicate error when a claim's modules go stale), configurable source
scope, the shared scan-context refactor, concept-level semantic detection
(`duplicate_concept`), and a meta-check that flags declared-but-unimplemented
policies (`spec_drift`, `missing_canonical_owner`, etc.).
