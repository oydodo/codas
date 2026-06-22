# Design — Paradigm preset mechanism (S3)

Implementable spec for the next session. Read `prd.md` + the epic ([[06-21-canonical-layout]]) first.
S3 is **data + rendering only — NO new policy, NOT gate-adjacent** (the corrected premise: all
policies already run; a preset takes effect by writing `structure.yml`). So no DESIGN review gate;
do a normal IMPL review after building.

## 1. What it produces (end state)

`codas init --paradigm clean-arch` on a fresh repo writes a `structure.yml` that, beyond today's root
catch-all, contains ONE example context's nested layer units (`status: planned`, placeholder paths) +
a `dependency_rules` inward chain + `canonical_placement` prose. `codas check` is GREEN (planned →
no `structure_drift`; placeholder paths own no files → `dependency_direction` inert until S4 maps real
paths). The user then renames the example context + maps paths (S4) to arm it.

## 2. Preset data model (curated YAML, §17-clean — no LLM, no facts)

Two shapes, chosen by `top_level`:

```yaml
# src/codas/presets/clean-arch.yml   (top_level: layers — a "technical-library" preset)
name: clean-arch
description: Clean architecture — dependencies point inward.
enforceable_for: [python]          # ecosystems the gate's resolver covers
top_level: layers                  # advisory label: framework/IO-shaped top level (NOT screaming)
roles:
  - {id: domain,         must_not_depend_on: [application, adapters, infrastructure],
     purpose: Enterprise business rules + entities.,
     canonical_placement: Pure business rules; no I/O or framework imports.}
  - {id: application,    must_not_depend_on: [adapters, infrastructure],
     purpose: Use-case orchestration.,
     canonical_placement: Coordinates domain; no adapters/infra imports.}
  - {id: adapters,       must_not_depend_on: [infrastructure],
     purpose: Controllers / presenters / gateways.,
     canonical_placement: Interface adapters; not infrastructure.}
  - {id: infrastructure, must_not_depend_on: [],
     purpose: DB / web / external I/O.,
     canonical_placement: Frameworks + drivers; outermost layer.}
```

```yaml
# src/codas/presets/ddd.yml   (top_level: contexts — the SCREAMING-shaped, default-recommended one)
name: ddd
description: Bounded contexts — each context is a vertical slice; layers nested inside; contexts isolated.
enforceable_for: [python]
top_level: contexts
layers:                            # SAME 4 roles, but replicated INSIDE each context (the "stamp")
  - {id: domain,         must_not_depend_on: [application, adapters, infrastructure], purpose: ..., canonical_placement: ...}
  - ...
cross_context: published-interface # marker only; the cross-context GATE is S5, not enforced here
```

Schema rules: `name` unique; `roles`/`layers` each have `id` + `must_not_depend_on` (subset of sibling
ids) + `purpose` + `canonical_placement`; `enforceable_for` non-empty; `must_not_depend_on` may not
reference unknown ids (validate at load → clear error). No paths, no domain names anywhere.

## 3. Loading (R2) — built-in + user + community, overridable

`app/paradigm.py`:
- `BUILTIN_DIR = <package>/presets/` — committed `.yml` data files (ship in the wheel; add to
  `[tool.setuptools.package-data]` or `include-package-data` so they install).
- `load_preset(repo, name) -> Preset`: search order **`.codas/presets/<name>.yml` (repo) → built-in**
  (user shadows built-in = overridable lazy default). `list_presets(repo) -> [(name, description, source)]`.
- A `Preset` dataclass (frozen) with validated fields. Parse with the existing pyyaml loader helper
  (mirror `config/loader.py`); no adapter import (§11 — this is `app/`).

## 4. Render algorithm (R3/R4) — preset → structure.yml fragment

`render_paradigm(preset, *, context="example_context") -> {units: dict, dependency_rules: dict, prose: str}`:
- roles (layers): for each role, emit unit id `f"{context}-{role.id}"`, path
  `f"src/{context}/{role.id}"` (placeholder), `kind: layer`, `owner: maintainers`, `purpose`,
  `canonical_placement`, **`status: planned`**.
- dependency_rules: `f"{context}-{role.id}": {must_not_depend_on: [f"{context}-{t}" for t in role.must_not_depend_on]}`.
- For `top_level: contexts` (ddd): same, plus a header comment "replicate this stamp under each real
  bounded context; cross-context isolation is enforced once you declare published interfaces (S5)".
- Keep the existing root catch-all unit (so `missing_structure_owner` stays inert — everything owned).
- Serialize DETERMINISTICALLY (sorted keys / fixed role order from the preset list), merged into the
  `_STRUCTURE` template. Prose → a leading comment block in the written structure.yml.

WHY planned + placeholder path (verified): `structure_drift` exempts `status: planned` (no error for
an absent path); `dependency_direction` resolves files to units by literal longest-prefix, and a
placeholder path owns no real files → the rule is inert → `codas check` GREEN. S4 later sets real
paths + flips `planned`→`active` to arm. (Alternative the implementer may prefer: write the fragment
as a COMMENTED template block instead of planned units — even more honest, but then it's not
codas-queryable until uncommented. Recommend planned units; note this fork.)

## 5. CLI (R3/R6)

- `init`: add `--paradigm <name>` (default `none`) + `--list-paradigms`. `none` = today's behavior
  unchanged. Wire in `cli.py` `init` branch → `app.init.scaffold(repo, force=, paradigm=)`.
- `scaffold(...)` gains `paradigm: str = "none"`; when set, load+render+merge into `_STRUCTURE` before
  writing. Keep no-clobber (don't overwrite an existing real structure.yml without `--force`).
- `codas paradigm list` (small new subparser) → `list_presets`. (Or fold into `--list-paradigms`.)

## 6. Ecosystem honesty (R5)

- `detect_ecosystems(repo) -> set[str]`: cheap, deterministic — `*.py`/pyproject → python; package.json
  → node; go.mod → go; etc. (Extend the W8a primitive if it exists, else add it here.)
- If `preset.enforceable_for ∩ detected == ∅`: still render, but mark every emitted unit's
  canonical_placement (or a header comment) "ADVISORY — codas's dependency gate does not enforce this
  for <lang>", AND print a CLI warning. Never present an unenforceable preset as gated.

## 7. §11 / §17 / determinism

- All new code in `app/` (`app/paradigm.py` + `app/init.py` edit); reads preset DATA + ecosystem facts;
  no `codas-adapters` import, no LLM. Preset files are committed curated data (like policy templates).
- Writing structure.yml is a user action (init), NOT part of `check`/`inventory` → no byte-identical
  concern for the write itself; but the render MUST be deterministic (sorted/fixed order) so repeated
  `init --force` is stable.
- New public symbols (`load_preset`/`render_paradigm`/`detect_ecosystems`/`Preset`/…) must not collide
  under `duplicate_implementation` (src/ scope) — check names are unique before finalizing.

## 8. Test plan

- preset load: built-in loads; user `.codas/presets/x.yml` shadows built-in; unknown id in
  `must_not_depend_on` → clear load error; missing required field → error.
- render: clean-arch → expected planned units + dependency_rules (exact assertion); deterministic
  (render twice byte-equal); root catch-all preserved.
- init integration (temp repo, git-init): `init --paradigm clean-arch` then `codas check` GREEN (no
  structure_drift, no dependency_direction findings since inert); `--paradigm none` == today;
  no-clobber honored.
- ecosystem: non-python repo (only package.json) → advisory marker + warning; python repo → enforce-labeled.
- `paradigm list` shows built-in + local.
- gauntlet: repo check 0; inventory byte-identical; agents/wiki --verify; full suite; symbol-collision check.

## 9. Decisions left to the implementer

- planned-units vs commented-template fragment (§4) — recommend planned units.
- placeholder context token (`example_context`) + placeholder path root (`src/`) — pick an
  obviously-fake, collision-proof token; document the rename step (→ S4).
- whether `codas paradigm list` is its own subcommand or `init --list-paradigms` (cosmetic).
- built-in preset set for v1: ship `clean-arch` + `layered` (technical-library) + `ddd` (screaming,
  recommended). Keep `hexagonal` for later or alias to clean-arch.
- the dogfood `.codas/structure.yml` `dependency_rules` block (codas-app/policies/core ¬dep
  codas-adapters) is a ready REAL hexagonal sample — use it as a render fixture / sanity reference.

## 10. Confirm before coding

The epic still rests on **context-as-unit (vertical, layers nested) over top-level layer units** —
confirmed by the path-prefix carrier + the screaming-DDD review. The `top_level: layers` presets
(clean-arch/layered) are offered but labeled technical-library; `ddd` (contexts) is the recommended
default. If the owner wants to drop the layer-shaped presets entirely, trim §2's first example.
