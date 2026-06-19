# Design — policy_registry consistency policy

## Policy algorithm (`policies/policy_registry.py::check_policy_registry(ctx)`)

```
declared = load_policies(ctx.repo / ".codas" / "policies.yml")["policies"]   # id -> entry dict
implemented = { name[len("check_"):]                                          # id
                for s in ctx.symbols().definitions
                if s.kind == "function"
                and s.name.startswith("check_")
                and (s.module == "src/codas/policies" or s.module.startswith("src/codas/policies/")) }

for id in sorted(implemented - declared.keys()):
    -> error "policy `check_<id>` is implemented but not declared in .codas/policies.yml"
       evidence: the policy module path (the symbol's module)
for id in sorted(declared.keys() - implemented):
    if entry(id).get("status") != "planned":
        -> error "policy `<id>` is declared in .codas/policies.yml but not implemented
                  (no check_<id>) and not marked `status: planned`"
       evidence: .codas/policies.yml
```

- **id derivation = the check FUNCTION name** minus `check_`, not the module filename
  (`missing_owner.py` → `check_missing_structure_owner` → id `missing_structure_owner`;
  `deprecated_path.py` → `deprecated_path_used`). Symbol facts carry the function name,
  so this is exact + deterministic.
- **Symbol scope** uses the `module` PATH prefix `src/codas/policies/` (symbol facts'
  `module` is a repo-relative path, per the D3a correction), so a `check_*` helper that
  ever appears elsewhere is out of scope. Top-level only (symbol facts are top-level),
  which is exactly the policy-entrypoint surface.
- **Self-registration:** `check_policy_registry` is itself an implemented symbol → it
  must be declared (governance). The registry registers itself; no special-casing.
- **Loads policies.yml directly** via `config.loader.load_policies` (a claim surface,
  like `duplicate_implementation` loads `claims.yml`) — not an adapter, §11-clean.
  Malformed policies.yml: `run_check` already emits `policy-load-error`; here, guard the
  load so a parse failure yields `[]` (no cascade / no crash), mirroring the existing
  best-effort policies (the load-error finding is owned elsewhere).
- **Severity error.** Markers read: only `status` (`"planned"` exempts a declaration
  from needing an impl). `kind: bootstrap` is descriptive (documents meta/loader checks
  vs governance rules); the policy does not branch on it.

## policies.yml reconciliation (to reach 0 on this repo)

Add the **7 bootstrap** entries (`kind: bootstrap`, with a one-line description):
`config_sources`, `document_set`, `dogfooding_protocol`, `program_plan`,
`structure_map`, `trellis_context`, `waivers`. Mark the **5 planned**
(`status: planned`): `duplicate_concept`, `orphan_artifact`, `missing_canonical_owner`,
`constraint_conflict`, `stale_preflight`. Declare **`policy_registry`** (governance).
After: declared = 23 (18 implemented incl. policy_registry + 5 planned); every
implemented id declared; every declared-non-planned id implemented → 0 findings.

This is the honest fix the doc-reconcile audit flagged: `policies.yml` becomes the
complete, accurate registry of what `check` actually runs, with planned items explicitly
marked rather than silently unimplemented.

## Wiring

- `check.py`: `findings.extend(check_policy_registry(ctx))` after
  `check_generated_wiki_drift` (18th policy, 8th ctx consumer).
- `test_codas_check.py` orchestration test: add `check_policy_registry` to the
  `mock.patch` set + the build-once-forward spy loop (the recurring trap — every new
  ctx-consuming policy must be patched there or the "built once" assertion breaks).
- `policies.yml`: the reconciliation above.

## Determinism / dogfood

- `policy_version` provenance hash moves (policies.yml changed) — correct, expected.
  **inventory byte-identical** (policies.yml is not an inventory fact). Confirm
  `inventory --json` unchanged across processes.
- Sorted finding emission (sort the two id sets) → deterministic order.
- New names unique: `check_policy_registry`, module `policy_registry.py`. (No collision
  with existing private helpers — verify `^def check_policy_registry` is the only
  match.)

## Tests (`tests/test_policy_registry.py`)

1. **0 on this repo** — `check_policy_registry(build_scan_context(cwd))` == [] (the
   reconciled registry is consistent).
2. **implemented-but-undeclared fires** — fixture ScanContext whose symbols include a
   `check_foo` under `src/codas/policies/` absent from a fixture policies.yml → 1 error.
3. **declared-but-unimplemented fires** — fixture policies.yml declares `bar` with no
   `check_bar` symbol and no `status: planned` → 1 error.
4. **`status: planned` exempts** — same as (3) but `bar: {status: planned}` → [].
5. **bootstrap/governance both require declaration** — an implemented check with a
   declaration (any kind) → no finding.
6. Orchestration test still asserts build-once + this policy patched (update existing).
7. check 0 + inventory byte-identical (the suite's standing invariants).

## Implemented (2026-06-20) + codex reviews folded

Shipped `policies/policy_registry.py::check_policy_registry(ctx)` + wired check.py
(18th policy, 8th ctx consumer) + reconciled policies.yml (7 bootstrap entries marked
`kind: bootstrap`, 5 planned marked `status: planned`, `policy_registry` declared
governance, top comment clarifying `severity` is nominal-not-runtime) +
`tests/test_policy_registry.py` (9 tests) + orchestration monkeypatch. 280 tests, `codas
check .` = 0, inventory byte-identical, `wiki --verify` clean.

- **Design review — APPROVE_WITH_CONDITIONS**, all met: (1) reconcile policies.yml
  atomically with wiring (same commit, dogfood never broken mid-PR); (2) orchestration
  monkeypatch added; (3) `severity` documented as declared/nominal, not runtime (a top
  comment in policies.yml; bootstrap dynamic-severity checks noted).
- **Impl review — APPROVE WITH NOTES.** Folded the NIT: a non-string YAML key (`1:`)
  in `policies:` survived the dict guard and could crash the mixed-type `sorted()` →
  now filter declared keys to strings (`declared_ids`), with a regression test. The
  SHOULD (a `check_*` implemented + declared but never wired into `run_check` is a
  silent no-op) is acknowledged v1 scope (dispatch-coverage is not symbol↔yml
  set-equality) — documented in the policy docstring + PRD out-of-scope; tightening to
  the check.py import/dispatch signal is a later refinement.

## Open questions (codex design pass)

1. id = strip-`check_`-prefix vs module filename — confirm function-name is the right,
   collision-free key (any two policy modules whose `check_*` strip to the same id?).
2. Should "implemented" be symbol-existence (this design) or check.py-import-wired?
   v1 picks symbol-existence (simpler, catches both documented drifts); is the
   defined-but-uncalled gap acceptable to defer?
3. Severity error vs warning — registry inconsistency is a governance hole; error (and
   reconcile to 0) vs warning (surface, don't block). Leaning error.
4. `kind: bootstrap` as pure documentation vs the policy enforcing that bootstrap checks
   are a known set — leaning documentation-only (no hardcoded list in the policy).
