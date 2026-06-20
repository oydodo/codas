# Design — fact-level co-change couplings (v2-B)

## What v2-A already gives us

`ScanContext.fact_delta() -> FactDelta` with `{symbols,imports,calls}_{added,removed}` as
sorted identity-key tuples (HEAD vs working tree), and `ScanContext.changed_paths()` (the
files in the same diff). Both are policy-time facts (not in inventory). A coupling policy
reads only these two — adapter-free, §11-clean.

## The mechanism

A **fact-level coupling** gates a co-change: *when a watched fact-delta is nonempty, a
required companion path must appear in the same diff.* It is the v1 `drift_couplings`
contract with the TRIGGER moved from a file-glob to a fact-delta predicate — which makes
it always-true (a comment fix produces no fact-delta → dormant).

```
fact_couplings:
  - when_fact:
      kind: symbol_added            # | symbol_removed | import_added | import_removed
                                    # | call_added | call_removed
      scope: src/codas/policies     # repo-rel path prefix the fact's module must be under
      name: "check_*"               # optional fnmatch on the fact's name/symbol identity
    requires:
      - .codas/policies.yml         # companion path/glob that must co-change
    owner: <responsible owner>
    reason: <why this co-change obligation holds>
```

Policy `check_fact_coupling(ctx)`:
1. `delta = ctx.fact_delta()`, `changed = ctx.changed_paths()`.
2. For each coupling, select the delta stream by `kind`; filter entries whose fact module
   is under `scope` and whose identity matches `name` (if given).
3. If any entry matches AND the coupling's `requires` paths are NOT all present in
   `changed` → one finding per missing requirement. Glob via the existing `_any_match`
   (fnmatch) already in `spec_drift`.
4. Empty delta or all-requirements-present → no finding. Deterministic total-key sort.

Identity keys (from v2-A): symbol `(module,name,kind)`, import `(module,target,
target_path)`, call 6-tuple. `scope`/`name` filter on these. `module` is a repo-rel path
(prefix match), `name` is the symbol/callee name.

## Scope: SURGICAL, not wholesale (the load-bearing decision)

The 24 `must_update_if_changed` entries are mostly `src/<unit>` → `docs/codas-
implementation-plan.html` (17×). **None of these has an always-true fact-level form**:
there is no fact-delta that means "the implementation plan is now stale" — a new private
helper, a refactor, a renamed local all touch facts but imply nothing about the plan doc.
Gating any "src changed → plan must change" coupling (file OR coarse-fact level) re-fires
on routine edits → breaks `check 0`. v1 correctly made these advisory; v2-B **keeps them
advisory** and does NOT promote them.

**Promotion criterion** (documented, the only couplings v2-B gates): a fact-delta D and a
companion C may be coupled iff *every* change producing D genuinely requires C — i.e. the
obligation is intrinsic to the fact change, not a heuristic about a document. These are
rare and specific (a registry that must mirror a symbol set; a manifest that must list a
new module).

## Worked example — the value a fact-delta gate adds over STATE policies

`policy_registry` (shipped, STATE/set-equality) already catches "a wired `check_*` lacks a
policies.yml entry" regardless of the diff — strictly stronger than a co-change gate for
that case. So the worked v2-B coupling must be a **DRIFT-only** signal: a change that needs
a companion even though the END STATE stays self-consistent (state policies see nothing).

Candidate: **a public symbol RENAME on an adapter fact type** (a `symbol_removed` of an
old public name + `symbol_added` of a new one under `src/codas/adapters`) **requires the
fact-vocabulary re-export site `src/codas/facts/context.py` to co-change** (its `__all__`
re-exports those names; a rename that doesn't update `__all__` leaves a stale export, but
the STATE is still importable via the adapter, so no state policy fires). This is a real
drift-only obligation grounded in the call/symbol delta.

(Open question for codex: is there a SHARPER always-true worked coupling on this repo?
The rename example needs both a removal and an addition to be unambiguous; a bare
`symbol_removed` of a public adapter name → `context.py __all__` must change is simpler
but fires on a genuine deletion too, which is correct. Pressure-test.)

## drift_couplings decision (proposed: RETIRE, fold into fact couplings)

`drift_couplings` (v1, file-glob trigger) is empty on the repo (resting 0-gate). Its
`{when_changed, requires}` is the file-level special case of `{when_fact, requires}`. Two
options:
- **RETIRE** `drift_couplings` + the `spec_drift` v1 policy; the new fact-coupling policy
  subsumes it. Cleaner; one mechanism. Risk: loses the ability to gate a pure
  file-co-change with no fact (e.g. "config A changed → config B must change") — but that
  is what the coarse advisory `must_update_if_changed` is for, and nothing uses it today.
- **KEEP** both: `spec_drift` (file-level vouched) for non-code co-change, the new policy
  for fact-level. More surface, but covers file-only couplings.
- Proposed: **RETIRE** (empty anyway; the §17 thesis is that the fact-level form is the
  right primitive). Re-add a file-level coupling only if a real need appears.

## Determinism / dogfood

- The policy adds NO finding on the clean tree (HEAD == working, nothing staged → empty
  delta → dormant). With a real coupling authored, a staged fact-change-without-companion
  fires; teeth proven by temp-git fixtures (real repos: commit, stage a fact change,
  assert the finding; stage the companion too, assert clean).
- Deterministic (sorted findings, fnmatch globs); inventory byte-identical (couplings are
  policy-time, never serialized); §17 (no LLM) / §11 (consumes ctx only) clean.
- New policy wired into `check.py` (Nth ctx consumer → the recurring orchestration-test
  monkeypatch in `test_codas_check.py` must patch it — the known trap). Declared in
  `.codas/policies.yml`. Unique helper names (grep `^def`).

## Open questions for codex (design review — BEFORE any gate change)

1. **Scope/appetite:** is "surgical (1 worked drift-only coupling + keep must_update
   advisory)" the right call, or should v2-B attempt a broader re-authoring? Argue from
   the gate-breaking risk. Is leaving `must_update_if_changed` advisory acceptable as the
   v2 end-state, or does the v2 thesis demand more?
2. **Worked coupling:** is the public-adapter-symbol-rename → `context.py __all__`
   co-change coupling genuinely always-true and dogfood-safe (0 on clean tree, fires only
   on a real uncoupled rename)? Is there a sharper one? Does it risk firing on legitimate
   changes (e.g. a rename that DOES update `__all__` in the same commit — should pass)?
3. **Schema surface:** author fact couplings in `.codas/claims.yml` (next to/replacing
   `drift_couplings`), in `.codas/structure.yml`, or a new `.codas/couplings.yml`? Which
   fits the §6 claim model + the loaders?
4. **drift_couplings:** retire (proposed) vs keep. Any real file-only co-change need that
   would be lost?
5. **fact_delta semantics for couplings:** `fact_delta()` is HEAD-vs-working (uncommitted
   work). Is gating uncommitted co-change the right model for a pre-commit hook, given
   `changed_paths()` is the same diff? Any mismatch where a fact moved but the file isn't
   in `changed_paths` (or vice versa) that breaks the "same diff" assumption?
6. Determinism / §11 / scope-creep holes.

## Codex design review folds (REWORK → resolved plan)

Codex confirmed SURGICAL is correct and RETIRE drift_couplings, but rejected the framing
and the worked coupling. The de-risked plan:

**B1 — drop "staged"/pre-commit framing.** Both substrates are HEAD-vs-working-tree
(`fact_delta()` diffs HEAD vs `working_snapshot()`; `changed_paths()` = `git diff HEAD` ∪
untracked). They share the SAME universe, so "watched fact changed AND companion in the
same diff" is internally consistent — but it gates the WORKING TREE, not the index. Call
it a "working-tree co-change" gate; document that it does not isolate staged-only changes
(an index substrate is out of scope). No "staged" language.

**B2/B3 — replace the worked coupling.** The adapter-rename example false-positives (the
adapters package also exports `TaskFact`/`TaskFacts` that `context.py` never re-exports)
AND can crash at import time (an uncoupled rename of a name `context.py` imports breaks
module load before the policy runs). DROP it.

**Adopted worked coupling (codex SHOULD-3, sharper + crash-free):**
> `symbol_added` of a `check_*` under `src/codas/policies` → `src/codas/app/check.py`
> must co-change.

`policy_registry` (STATE) verifies a `check_*` symbol is DECLARED in `policies.yml`, but
NOT that `check.py` WIRES/calls it — so a new policy added + declared but left unwired
passes every state check yet never runs (a dead gate). The fact-coupling catches that
drift. Always-true (a new `check_*` policy must be wired), drift-only (state stays
consistent), no import-crash path (`check.py` is the companion, not an import chain
through the renamed symbol). Dogfood-safe: clean tree → empty delta → dormant; adding a
`check_*` without touching `check.py` → fires; touching both → clean.

**Should-2 — schema in `.codas/claims.yml`.** A new `fact_couplings:` block beside the
(retired) `drift_couplings`; `load_claims()` already owns the loader and the §6 claim
model. NOT a new file, NOT `structure.yml` (whose `must_update_if_changed` is by-schema
advisory).

**Should-4 — malformed coupling = ERROR, not silent skip.** v1 `spec_drift` silently
ignores malformed entries; for a hard gate that silently DISABLES it (worse than
advisory). The new policy emits an error finding on a malformed `fact_couplings` entry
(missing/!str `when_fact.kind`/`scope`/`requires`), so a typo can't quietly turn the gate
off.

**RETIRE drift_couplings + spec_drift v1.** Remove `check_spec_drift`, its
`drift_couplings` block + claims.yml comment, the policies.yml `spec_drift` declaration
(replace with `fact_coupling`), the check.py wiring (replace), and migrate/retire the
spec_drift tests. Update the orchestration monkeypatch in `test_codas_check.py` (the
recurring trap). `policy_registry` must stay 0: removing `check_spec_drift` and adding
`check_fact_coupling` means `policies.yml` must drop `spec_drift` and declare
`fact_coupling` in the SAME change (and — fittingly — this very change is an instance of
the kind of coupling the new policy gates).

**Promotion criterion (documented, Should-1).** A `must_update_if_changed` entry graduates
to a hard `fact_couplings` gate ONLY when a specific fact-delta makes the companion
obligation always-true (every change producing the delta genuinely requires the
companion). The coarse `src → impl-plan.html` entries do not qualify and stay advisory.

**Nits.** "working-tree fact change" not "staged"; brand `fact_couplings` as the
drift_couplings successor only with B1 documented.

## Implementation order (post-fold)

1. `policies/fact_coupling.py::check_fact_coupling(ctx)` — read `claims.yml`
   `fact_couplings`; select delta stream by `kind`; filter by `scope` prefix + optional
   `name` fnmatch on the identity; malformed entry → error finding; a matched delta with a
   `requires` path absent from `changed_paths()` → error finding. Deterministic sort.
2. `.codas/claims.yml` — drop `drift_couplings` (+ its comment); add `fact_couplings` with
   the ONE live policy-registration coupling.
3. Retire `policies/spec_drift.py` + its tests; `.codas/policies.yml` spec_drift →
   fact_coupling; `app/check.py` rewire; `test_codas_check.py` orchestration patch.
4. Tests: `test_fact_coupling.py` (malformed→error; clean tree→0; temp-git fixture: add a
   `check_*` without check.py → finding, with check.py → clean; non-policy edits → 0).
5. Verify: check 0, inventory byte-identical, full suite, wiki --verify; codex impl review.
