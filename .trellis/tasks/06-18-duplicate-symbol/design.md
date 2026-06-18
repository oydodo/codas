# Design: Duplicate symbol policy

## Policy (`src/codas/policies/duplicate_symbol.py`)

Signature: `check_duplicate_symbol(repo: Path, config: CodasConfig) -> list[Finding]`

Consumes symbol facts directly (no full inventory build):
```
roots = workspace_roots(config.raw)
files = discover_files(repo, roots)
facts = extract_symbol_facts(repo, tuple(files))

# scope: public top-level symbols in src/ implementation modules
scoped = [
    d for d in facts.definitions
    if d.module.startswith(SObundsRC := "src/")   # implementation source only
    and not d.name.startswith("_")                # public only
]

by_name: dict[str, list[SymbolFact]] = group by d.name (preserve fact order)
findings = []
for name in sorted(by_name):
    occ = by_name[name]
    modules = sorted({d.module for d in occ})
    if len(modules) < 2:
        continue
    evidence = [Evidence(path=d.module, line=d.line, detail=d.kind)
                for d in sorted(occ, key=lambda d: (d.module, d.line))]
    findings.append(Finding(
        severity="warning",
        check_id="duplicate-symbol",
        message=f"Public symbol '{name}' is defined in {len(modules)} modules: {', '.join(modules)}",
        evidence=evidence,
        recommendation=("Consolidate into one definition, declare a "
                        "canonical/variant/migration relationship, or add a waiver."),
        meta={"name": name, "modules": modules},
    ))
findings.sort(key=lambda f: f.meta["name"])
return findings
```
(`SCOPE_PREFIX = "src/"` constant, not the inline walrus above — illustrative.)

Rationale recap:
- **public only** — a leading-underscore module-level helper (`_rel`, `_mapping`)
  is local-by-convention encapsulation, not a duplicate *implementation*. Probe
  confirms every cross-module repeat on this repo is private; scoping to public
  keeps the dogfood invariant AND matches the §10 intent ("type/function names",
  i.e. real API surface).
- **`src/` only** — duplicate *implementation* concerns governed source. `tests/`
  intentionally repeats helpers across files; `.trellis/scripts` is vendored.
  Both excluded by the prefix. `src/` == `src/codas` on this repo.
- **group by name** (not name+kind) — a name collision is suspicious regardless
  of class-vs-function; `kind` is carried in evidence `detail` for context.
- **count distinct modules** — two top-level defs of the same name in ONE module
  (legal? no — Python rebinds; the second wins) are not cross-module duplication;
  require ≥2 distinct modules.

Severity = `warning`: same-name is a deterministic *candidate* signal, not proof
of duplicate implementation (two unrelated `run()` funcs can coincide). The
error-severity, claim-aware `duplicate_implementation` is deferred until a
relationship-claim store exists. policies.yml `duplicate_concept` stays `error`
(semantic level, later).

## policies.yml addition

```
  duplicate_symbol:
    severity: warning
    description: Public top-level type or function names repeated across src modules are flagged as candidate duplicate implementations; consolidate, declare a canonical/variant/migration relationship, or waive. Concept-level semantic detection is later.
```
Placed near `duplicate_concept`. This is the claim source for the new behavior;
`duplicate_concept` is left intact as the documented semantic-level policy.

## Wiring (`src/codas/app/check.py`)

Append after the structure policies / before or after waivers — ordering is
cosmetic (report groups by severity):
```
findings.extend(check_duplicate_symbol(repo, config))
```

## Determinism

`extract_symbol_facts` returns a sorted tuple; scoping preserves order; grouping
iterates sorted names; evidence sorted by `(module, line)`; findings sorted by
name. No timestamps. The policy adds no inventory fields, so inventory stays
byte-identical.

## Tests (`tests/test_duplicate_symbol_policy.py`)

Temp repo, write `.codas/config.yml`-free `CodasConfig(raw={})` (default root `.`)
and `.py` files under `src/`:
- same public `def handle()` in `src/a.py` and `src/b.py` → one warning finding,
  evidence has both modules+lines, sorted; meta.modules == ["src/a.py","src/b.py"].
- same public `class Widget` in two src modules → flagged (class kind in evidence).
- a `_helper` repeated across two src modules → NOT flagged (private).
- a public name in only one module → NOT flagged.
- a public name repeated only under `tests/` (e.g. `tests/x.py`, `tests/y.py`)
  → NOT flagged (out of `src/` scope).
- a public name repeated under `.trellis/scripts/` → NOT flagged.
- determinism: two duplicated names → findings sorted by name.

Plus the dogfood-invariant test in `test_codas_check.py`: assert `duplicate-symbol`
absent from `codas check .`.

## Follow-ups (from codex design review, deferred — none are blockers)

- **Private-symbol pass** (#1): this policy covers public-API candidates only;
  a genuinely duplicated *private* API is not detected. Track a later private /
  signature-aware pass. The description scopes the claim honestly ("public … type
  or function names").
- **Config-driven source scope** (#2): `SCOPE_PREFIX = "src/"` is hardcoded. On
  this repo `src/` is the only implementation `.py` tree, so it is exhaustive
  here, but code outside `src/` (e.g. a future `scripts/*.py`) is a silent
  false-negative. Later: a `duplicate_symbol.source_prefixes` policy setting (or
  derive from structure units) defaulting to `["src/"]`.
- **Policy lifecycle annotation** (#3): `.codas/policies.yml` declares several
  policies that are not implemented (`duplicate_concept`, `spec_drift`,
  `missing_canonical_owner`, `constraint_conflict`, `stale_preflight`). Codas does
  not yet flag declared-but-unimplemented policies on itself — a real self-
  spec_drift gap. Later: a lifecycle field (e.g. `status: planned`) plus a meta
  check, and a name mapping `duplicate_implementation → duplicate_symbol (P2 first
  cut)` / `duplicate_concept (semantic, later)`.
- **Error-level, claim-aware `duplicate_implementation`** (#4, #7): warning here
  is a candidate signal. Promotion to the schema §8 error rule ("a second
  implementation lacks a declared relationship") is blocked on a
  canonical/variant/migration claim store (the suppression mechanism). Until then
  the waiver system is the only escape hatch. Track before any error promotion.
- **Shared scan context** (#6): this policy re-runs `discover_files` +
  `extract_symbol_facts` independently, like the prior slices. The accumulating
  shared-scan refactor (one scan passed to all policies via the check runner) is
  still the right eventual fix.

## Dogfooding checklist

- Concept: new `duplicate_symbol` policy (plan §10). Claim source updated
  (`.codas/policies.yml` gains the declaration) so behavior matches the claim —
  no `spec_drift` against our own config.
- New artifacts: `src/codas/policies/duplicate_symbol.py` (governed by
  `codas-policies`), `tests/test_duplicate_symbol_policy.py` (`codas-tests`).
  `inventory.unowned` stays empty.
- No new module dir → no structure.yml unit edit. No plan/schema edit (the policy
  realizes the already-authoritative §10 `duplicate_symbol` row).
- Bootstrap gate: `unittest discover` + `git status --short` clean.
- Link `program:P2:policy-engine-structure-drift` → this task.
