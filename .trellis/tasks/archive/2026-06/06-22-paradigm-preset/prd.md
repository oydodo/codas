# Paradigm preset mechanism (S3) — `codas init --paradigm` writes context-shaped dependency constraints

S3 of the paradigm-onboarding epic ([[06-21-canonical-layout]]). Read that epic PRD's decision
record + the MECHANISM CORRECTION first; read `design.md` (this task) before coding.

## Goal

`codas init --paradigm <X>` seeds a repo with a **context-shaped dependency-constraint template** —
nested layer units + a `dependency_rules` block + `canonical_placement` prose — so the existing,
already-running `dependency_direction` policy enforces the paradigm with **no new gate**. The
paradigm owns the skeleton (roles + inward-only deps); the project owns the naming (context + paths,
filled later by S4). Presets are curated, overridable DATA, ecosystem-honest.

## Key premises (verified — do not re-litigate)

- **All policies run unconditionally** (`app/check.py:61-79`); `policies.yml` is NOT an enable switch.
  So a preset takes effect purely by writing `units` + `dependency_rules` into `structure.yml`.
- **Carrier shape** (`structure/loader.py`): `units` need `path/kind/owner/purpose/canonical_placement`
  (+ optional `status: planned`, exempt from `structure_drift`); `dependency_rules:` is a SEPARATE
  top-level block (`unit-id → {must_not_depend_on / may_depend_on: [unit-ids]}`).
  `dependency_direction` resolves importer/target by LONGEST literal path-prefix → a unit must be a
  CONTIGUOUS path subtree. ⇒ unit = a CONTEXT (vertical, contiguous), layers NESTED inside
  (`orders/domain` ¬dep `orders/adapters`), NOT top-level layers.
- **Python-only resolver** (`adapters/callgraph.py` + `python_parse.py`): a preset on a non-Python
  repo enforces NOTHING → must be written advisory + said so (false-confidence is worse than nothing).

## Requirements

- **R1 — preset data model.** A preset is a curated YAML file describing a paradigm as: nested layer
  ROLE ids + the inward `must_not_depend_on` edges among them + `canonical_placement` prose templates
  per role + an `enforceable_for` ecosystem tag. NO concrete paths, NO domain names. Pure data, no LLM
  (§17). See design.md for the exact schema.
- **R2 — built-in + user + community loading.** Built-in presets ship in-package (a tuple/dir);
  user/community presets load from `.codas/presets/<name>.yml` (repo) and/or `~/.codas/presets/`;
  a user preset shadows a built-in of the same name (overridable lazy defaults).
- **R3 — `codas init --paradigm <X>`** renders the preset into the scaffolded `structure.yml` as ONE
  example context's nested layer units (`status: planned`, placeholder context path) + the matching
  `dependency_rules` block + the canonical_placement prose. `--paradigm none` (default) = today's
  minimal skeleton, unchanged. `codas init` stays no-clobber (don't overwrite a real structure.yml
  without `--force`).
- **R4 — context STAMP, not a repo cap.** The rendered units describe ONE example context with layers
  nested inside it; the prose explains the discipline + "replicate this stamp per context". Do NOT seed
  top-level layer units. Planned + placeholder path so a fresh `codas check` is GREEN (no
  structure_drift, dependency_direction inert until S4 maps real paths).
- **R5 — ecosystem honesty.** Detect the repo's language (reuse/extend the W8a ecosystem-detect
  primitive); if no Python resolver covers it, render the preset but mark it advisory and PRINT that
  `dependency_direction` will not enforce it for this language (CLI + a note in the scaffold).
- **R6 — discoverability.** `codas paradigm list` (or `codas init --list-paradigms`) prints the
  available built-in + local presets with one-line descriptions.
- **R7 — §11/§17 + determinism.** Preset rendering lives in `app/` (or `app/init`), reads preset DATA
  (no adapter, no LLM); the scaffolded YAML is deterministic (sorted/fixed order). Built-in preset
  files are committed data. `codas check .` 0; inventory byte-identical; suite green.

## Acceptance Criteria

- [ ] `codas init --paradigm clean-arch` in a fresh repo writes a structure.yml with a planned
      example-context's nested layer units + a `dependency_rules` inward chain + canonical_placement
      prose; `codas check .` is GREEN (no structure_drift; dependency_direction inert pre-mapping).
- [ ] At least 2 built-in presets ship (e.g. `clean-arch`/`hexagonal` + `layered`), each labeled
      "technical-library preset" where the top level is framework/IO-shaped (per the epic's screaming
      caveat); a `ddd`/context preset is the screaming-shaped default-recommended one.
- [ ] A user `.codas/presets/<name>.yml` loads and shadows a built-in of the same name.
- [ ] On a non-Python repo, `--paradigm` renders advisory + prints the enforcement-off warning.
- [ ] `codas paradigm list` shows built-in + local presets.
- [ ] Determinism gauntlet: this repo's `check` 0, inventory byte-identical, agents/wiki --verify
      clean, full suite green; new public symbols don't collide (duplicate_implementation).

## Out of scope (other epic sub-tasks)

- S4 role→path mapping + existing-repo import-cluster suggestion + planned→active arming.
- S5 cross-context published-interface gate; S6 role-membership / catch-all gate (both gate-adjacent →
  DESIGN review first).
- npx wrapper / PyInstaller binary (roadmap).
