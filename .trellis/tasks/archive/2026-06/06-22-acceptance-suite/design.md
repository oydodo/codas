# Acceptance suite — whole-product verification (design / charter)

## 0. Purpose

563 unit tests exist; they test **components in isolation** (call `check_<policy>` directly,
hand-roll a structure.yml string, assert one finding). They do NOT prove the **product**
behaves end-to-end against the PRD. Two real bugs (the CLI argparse `dest` collision and the
`exec VAR=val` hook bug) shipped past the unit suite because they lived only on the
integration surface; the dogfood caught them, not a test.

This suite is the layer **above** the unit tests: it drives Codas through its **public
entry points only** (`run_check`, the `python -m codas …` CLI, `codas wiki --verify`, the
hook envelope) against **synthetic whole repos**, and traces each assertion to a PRD
requirement (program.yml exit_criteria + design.html §22 Acceptance / §25 Normative).

Non-goal: replace the unit tests. Acceptance is coarse-grained, end-to-end, few-but-load-bearing.

## 1. Architecture — 11 modules, layered bottom-up

```
  M7  自治理/dogfood — Codas passes its own gate (capstone)            = today's CI
  M8  跨仓库 — foreign-layout repo: init→check→render all work; no hardcoded paths  (cross-cut)
  M9  接线完整 — every `python -m codas <cmd>` subprocess: exit code + shape   (cross-cut)
  M10 套件有牙 — mutation: break a policy/adapter → ≥1 test must fail          (cross-cut)
  ── product capabilities ──────────────────────────────────────────────────
  M6  Agent 接口 — JSON contracts / preflight pack / per-turn injection / AGENTS.md
  M5  Enforcement — doctor live-probe / git hooks block / CI / init scaffold
  M4  派生物 — wiki/book/AGENTS render = deterministic projection + --verify pos/neg + no hash leak
  M3  合规 — waiver suppression / expired-waiver / exit-code severity semantics / conflict priority
  M2  ★Gate 矩阵 — 20 policies fire through full run_check at catalog severity; clean=0; coverage-as-gate
  M1  ★事实提取 — known source → exact fact set; open-world soundness (absence ≠ denial)
  M0  地基 — inventory byte-identical 2× / provenance hash separation / receipt ledger
  ── all built on ──────────────────────────────────────────────────────────
      tests/_repo.py  — the golden-repo builder (shared by M0–M9)
```

| module | PRD ref | accepts (one line) | today | priority | new/fill |
| --- | --- | --- | --- | --- | --- |
| M0 foundation | P1/P4 §9 | same repo → same hash; fact-vs-policy provenance separate | strong | low | fill |
| M1 fact extraction | P1 §9.1/§9.4 | known source → exact facts; open-world lower bound | partial | **high** | new |
| M2 gate matrix | P2/P3 §11 | 20 policies fire through run_check at catalog severity; clean=0 | unit-only | **high** | new |
| M3 compliance | §12/§13/§17 | waiver suppresses; expired doesn't; error→exit1/warn→exit0; conflict priority | partial | med-high | new+fill |
| M4 derived artifacts | P5/P8 §14 | render = deterministic; --verify pass-fresh/fail-tampered; no hash leak | strong | low | fill (enforcement --verify) |
| M5 enforcement | P6 §18 | install → bad commit blocked; doctor sees installed/foreign/absent; init → valid skeleton | good | low | fill |
| M6 agent interface | P7 §18 | JSON shape stable (codas schema self-describes); impact correct; injection fires+dedups | good | low | fill |
| M7 self-governance | §20 | Codas check 0 on self + registry 1:1 + byte-identical + --verify | = CI | low | have |
| M8 cross-repo | P8 cross-repo | foreign-layout repo: init→check→render all work; no hardcoded paths | partial | med | new+fill |
| M9 wiring | §7 product shape | every CLI command subprocess: exit code + output shape | weak | med-high | new |
| M10 potency | meta | mutation kills ≥1 test per mutant | none | med (nightly) | new |

## 2. The shared harness — `tests/_repo.py`

The keystone. Without it the matrix is unwritable. Kills the 49 hand-rolled `_write/_ctx`
helpers + 300 ad-hoc tempdirs.

### 2.1 API (proposed)

```python
@dataclass
class GoldenRepo:
    root: Path
    def write(self, relpath: str, content: str) -> Path   # create/overwrite a file
    def remove(self, relpath: str) -> None
    def commit(self, msg: str = "seed") -> None           # git add -A && git commit
    def check(self) -> CheckReport                        # in-process run_check(self.root)
    def cli(self, *args: str) -> subprocess.CompletedProcess  # python -m codas <args> (M9)
    def kinds(self) -> set[tuple[str, str]]               # {(check_id, severity)} convenience

def build_golden(tmp: Path) -> GoldenRepo:
    """A MINIMAL, VALID, zero-finding, git-committed Codas repo."""
```

### 2.2 Golden-repo contents (minimal but complete enough to host every mutation)

- `.codas/config.yml` — product_roots, authoritative+supporting sources, book_root.
- `.codas/structure.yml` — synthetic minimal units: one src package unit, `.codas` governance
  unit, docs, `.trellis`. Self-describing (NOT a copy of the real map). ⚠️ **B3 — NO repo-root
  (`.`) catch-all unit in the M2 ownership profile:** a `.` path normalizes to an empty prefix
  that owns EVERY file (`structure/index.py:112-120`, pinned by `test_missing_owner_policy.py:
  85-92`), so missing_structure_owner could never fire. The clean-baseline profiles may keep a
  root unit; the missing_owner case profile must omit it and instead leave one path unowned.
- `.codas/program.yml` — one valid work_item.
- `.codas/documents.yml` — all canonical-required roles present + the role files on disk.
- `.codas/policies.yml` + `src/codas/policies/*.py` stubs — ⚠️ **B1 — policy_registry scans the
  TARGET repo's `src/codas/policies/` tree** for `check_*` symbols (`policy_registry.py:22-29,
  61-68`), NOT the installed package. A golden that declares the real policy set but ships no
  `src/codas/policies/check_*` defs self-fails with declared-but-unimplemented `policy-registry`
  errors. **Fold (see Q1):** do NOT put a full policies.yml in the golden. Either (a) the golden
  ships a tiny `src/codas/policies/` with matching `check_*` stubs + a matching minimal
  policies.yml, OR (b) the policy_registry case + the severity-catalog read are tested OUTSIDE
  the golden (against the REAL repo's `.codas/policies.yml`). Lean (b): keep the golden's
  registry surface minimal/empty and read declared severities from the real catalog.
- `.codas/waivers.yml` — empty/valid.
- `.codas/claims.yml` — valid (may carry one duplicate-impl claim for the M2 #5 case).
- `src/<pkg>/*.py` — a couple of owned modules with clean public symbols.
- `.codas/wiki/generated/*.md` — one valid generated page (fresh atlas:claims) — needed for
  generated_wiki_drift-clean and the #12 mutation. Built by calling `codas wiki --write` on
  the golden during construction (so it is genuinely fresh), then asserted clean.
- `.codas/wiki/code/*.md` — one code-wiki page whose `defines:` anchors resolve.
- `docs/` — the required-role docs.
- `.trellis/` — tasks root + one task (PRD present).

### 2.3 The isolation principle (the hard part)

A governed repo is interdependent — deleting structure.yml trips structure_map AND
missing_owner AND policy_registry. So **every M1–M8 case = golden + ONE mutation**, and the
assertion is:

- MUST (loose): the target finding `(check_id, severity)` is present.
- SHOULD (strict, opt-in per case where feasible): `errors(mutated) - errors(golden) ==
  {target_check_id}` — no collateral error introduced. NOT mandatory; some violations
  legitimately cascade.

## 3. M2 — gate conformance matrix (detail)

20 implemented policies → one case each (multi-kind policies get one per variant). Driven by
full `run_check(golden+mutation)`. Two assertions per case:

1. `(check_id, severity)` present in report → **P1 fires**.
2. `severity == declared_severity(policy)` where `declared_severity` is read at test time from
   the target repo's `.codas/policies.yml` (`load_policies`), NOT hardcoded → **P3 fidelity**.
   Rule: governance policies emitted `==` declared; bootstrap (`kind: bootstrap`) emitted `<=`
   declared (policies.yml explicitly allows loaders to emit lower).

Plus golden: `build_golden().check().findings == []` → **P2 aggregate clean**.

### 3.1 Case table (mutation → expected finding)

Governance (13):

| policy | mutation on golden | check_id | sev |
| --- | --- | --- | --- |
| missing_structure_owner | add a file no unit owns | missing-structure-owner | error |
| structure_drift | a unit path points to a missing dir | structure-drift | error |
| deprecated_path_used | mark a path deprecated, add a file under it | deprecated-path-used | error |
| dependency_direction | add a forbidden `import` (owner must_not_depend_on) | dependency-direction | error |
| duplicate_symbol | two modules define same public symbol **with** a claim | duplicate-symbol | warning |
| duplicate_implementation | same two modules **without** a claim (rides + the warning) | duplicate-implementation | error |
| stale_claim | a .md broken link `[x](./nope.py)` | stale-claim | warning |
| stale_html_claim | an authoritative .html `<a href>` to a missing path | stale-html-claim | warning |
| stale_wiki_claim | a wiki canonical_source neither authoritative NOR supporting (pick ONE variant; missing canonical_source/evidence/sync_target paths also fire) | stale-wiki-claim | warning |
| fact_coupling | claims a symbol→path coupling; working tree changes symbol only | fact-coupling | error |
| code_anchor | a code-wiki `defines:` to a non-existent symbol | code-anchor | warning |
| generated_wiki_drift | edit a generated page `unit:` path or `roadmap:` status claim to contradict facts (only unit/roadmap kinds checked; source-hash freshness is NOT a run_check finding) | generated-wiki-drift | error |
| policy_registry | declare a non-planned policy with no implementation | policy-registry | error |

Bootstrap (7):

| policy | mutation | check_id | sev |
| --- | --- | --- | --- |
| config_sources | config declares a missing **authoritative** source (supporting → warning) | declared-source-missing | error |
| structure_map | malformed structure.yml | structure-map-loads | error |
| program_plan | malformed program.yml | program-plan-loads | error |
| document_set | remove a required-role doc (path NOT also a declared source — else config_sources pre-empts) | document-set-complete | error |
| trellis_context | remove `.trellis/tasks` root | trellis-tasks-root-missing | error |
| dogfooding_protocol | point dogfooding.protocol at a missing file | dogfooding-protocol-target-missing | error |
| waivers | a waiver missing `expires` (or with a past `expires`) | waiver-schema-invalid | error |

### 3.2 The dup pair (#5/#6) — coupled by design

A repeated public symbol fires BOTH duplicate_symbol (warning, detection signal) and
duplicate_implementation (error, enforcement). Isolate via claims.yml: WITH a relationship
claim → only the warning; WITHOUT → the error appears (+ the warning rides). This also tests
claim-suppression of duplicate_implementation.

### 3.3 fact_coupling (#10) needs a real git diff

It compares working-tree facts vs HEAD. So that case: commit the golden, then mutate the
working tree (add/remove the watched symbol) WITHOUT touching the required companion path.
The golden builder's `commit()` enables this.

### 3.4 Coverage-as-a-gate (the self-maintaining property — the thing missing today)

A meta-test: `set(CONFORMANCE_CASES.policies) == implemented_governance_policies()`. → a new
policy without a fires-on-violation case fails CI. Planned policies (5) excluded.

⚠️ **B2 — cannot reuse `check_policy_registry` directly.** That function is a `ScanContext`-
coupled policy that scans a repo tree for `check_*` symbols under `src/codas/policies/` and
includes bootstrap checks (`policy_registry.py:45-68`) — wrong abstraction for a meta-test over
the INSTALLED modules. **Fold:** extract a pure helper `discover_implemented_policies()` (no
ScanContext; introspect the installed `codas.policies` package's `check_*` functions) and have
BOTH `check_policy_registry` and the coverage meta-test consume it = one real source of truth.
That refactor is a prerequisite sub-step of the M2 task.

## 4. M3 — compliance & conflict (extends M2)

⚠️ **B6 — waiver suppression DOES NOT EXIST today.** `check_waivers` only validates waiver
schema (id/reason/owner/`expires` present + `expires` not past, `waivers.py:23-39`); `run_check`
APPENDS its findings and never filters earlier findings (`check.py:107`). `provenance.py:23`
states it outright: *"waivers.yml (which suppresses findings) is out of scope for now."* But PRD
§17 promises a violation can be bypassed by a valid waiver. So M3 must NOT test suppression —
it would assert behavior the product lacks.

M3 therefore tests CURRENT behavior + flags the gap:

- **Waiver schema (§17, EXISTS):** golden + an invalid waiver (missing `expires`, or past
  `expires`, or non-list) → `waiver-schema-invalid` error. Valid waiver → no finding.
- **Exit-code semantics (§11.1, EXISTS):** via M9 CLI — a repo with only a warning →
  `codas check` exit 0; a repo with an error → exit 1.
- **Conflict priority (§13):** constraint_conflict is `planned` (no impl) → covered only by the
  registry-inert assertion. Skip until implemented.

**PRODUCT GAP surfaced by this review (→ separate task, NOT this suite):** waiver SUPPRESSION
is PRD-promised (§17) but unimplemented. Until it ships, an acceptance test `test_valid_waiver_
suppresses_finding` should be written **xfail/skip with a pointer to the gap task**, so the
suite documents the missing promise instead of silently omitting it. Building suppression =
its own product task (wire a waiver→finding matcher into `run_check`'s result before
severity-aggregation).

## 5. M1 — fact-extraction golden (the ground under M2)

M2 assumes facts are right. M1 proves it. A small fixed source tree → assert the EXACT fact
set Codas extracts:

- symbols (top-level defs/classes, public/private), imports (first-party resolution-tagged),
  calls (call edges, resolution-tagged, open-world lower bound), doc_claims, html_claims,
  wiki_claims, trellis task facts.
- **Open-world soundness (§9.4):** a dynamic/conditional call the extractor misses must be
  ABSENT, never falsely asserted; assert the extractor never emits a fact the source does not
  support (no false positives), and document which absences are expected (the lower-bound
  caveat). This is the soundness half the gate's correctness rests on.

Approach: a `tests/acceptance/fixtures/facts_golden/` source tree + an expected-facts JSON;
assert `build_inventory(fixture)` facts == expected (byte-stable, already deterministic).

## 6. M9 — wiring / surface integrity

For every CLI command (`check`, `inventory`, `preflight`, `status`, `doctor`, `agents`,
`wiki`, `query`, `impact`, `schema`, `hooks`, `init`, `claude-hook`): drive the REAL
`python -m codas <cmd>` subprocess against the golden and assert exit code + output shape
(JSON parses, expected keys). This is the layer that would have caught the 2 shipped CLI bugs.
Runs the installed entrypoint exactly as an agent/CI would. ⚠️ **S6 — assert shape, NOT
byte-identical stdout:** CLI output carries repo paths / git state / renderer text that vary
across environments; full stdout snapshots would be flaky. Stop at exit-code + JSON-parses +
expected-keys-present.

## 7. PRD traceability (cross-cutting requirement)

Each acceptance module opens with a `# Traces:` block mapping its cases to PRD requirements:
program.yml `exit_criteria` per phase + design.html §22 Acceptance Criteria + §25 Normative
Requirements (the formal MUST list). A coverage report (which §25 MUSTs have an acceptance
test) is a deliverable — today no such traceability exists.

## 8. CI integration

Today: `unittest discover` + `check` + `agents --verify` + `wiki --verify` (= M7).
Add: an `acceptance` job running `tests/acceptance/` (M0–M9, fast, in-process + subprocess);
a SEPARATE nightly non-blocking job for M10 mutation (slow). Also wire `enforcement --verify`
(or document "the byte-compare test is the guard") to close the known M4 gap.

## 9. Build sequence (each = a child Trellis task)

1. `tests/_repo.py` golden-repo builder — pure enabler, no behavior change. FIRST.
2. M2 gate matrix (+ M3 waiver suppression) — highest value; gate-adjacent → DESIGN review.
3. M1 fact-extraction golden — the ground under M2.
4. M9 CLI subprocess — cheap, catches real bugs.
5. M0/M4/M5/M6 gap-fills — small.
6. M8 cross-repo + M10 mutation (nightly) — hardening.

Each step is independently valuable; no big-bang.

## 10. Open questions — RESOLVED by the DESIGN review

- **Q1 — golden policies.yml sync.** Do NOT copy the real `.codas/policies.yml` into the golden
  unless the golden also ships matching `check_*` stubs. SPLIT the registry/severity-catalog
  tests out of the golden: test policy_registry + read declared severities against the REAL
  repo's catalog; keep the golden's registry surface minimal. (See §2.2 B1 fold.)
- **Q2 — golden complexity.** Use PROFILES, not one rich golden (too fragile as policies
  evolve). `build_golden(profile="check")` minimal for M2; add `wiki`/`agent`/`full` only where
  needed. The M2 ownership profile omits the root catch-all (B3).
- **Q3 — strict isolation.** Target-present alone is too weak. Use target-present PLUS
  "no unexpected error check_ids," with a documented allowed-collateral list per case for known
  malformed-config cascades.
- **Q4 — severity fidelity.** Keep governance `==` declared / bootstrap `<=` declared, BUT
  assert the per-trigger emitted severity EXPLICITLY (bootstrap has real dynamic lower-severity
  variants: supporting config source → warning, missing dogfooding protocol → warning, missing
  Trellis context).
- **Q5 — generated pages.** Generate via `codas wiki --write` during fixture construction, then
  assert SEMANTIC claims (not renderer byte snapshots). Static pre-rendered pages rot and hide
  renderer/verifier disagreement.
- **Q6 — mutation scope.** Scope M10 first to `src/codas/policies`, `app/check.py`, and the
  facts/adapters that feed policy triggers. Operators: drop-a-finding, change check_id/severity,
  invert a trigger predicate, remove a `run_check` policy call.
- **Q7 — unit/acceptance overlap.** Keep BOTH. Acceptance proves public behavior through
  run_check/CLI; unit tests still cover branch-level edge cases impractical through the stack.
- **Q8 — placement.** `tests/acceptance/` + `tests/_repo.py` + `tests/acceptance/fixtures/` all
  under the existing `codas-tests` unit; run `codas check .` after adding to confirm no
  structure-map update needed.

## 11. DESIGN review record (codex, 2026-06-22)

**Verdict: NEEDS-REWORK** → all 6 blockers verified against source + folded above.

| id | finding | status |
| --- | --- | --- |
| B1 | golden policies.yml premise false — policy_registry scans TARGET repo's `src/codas/policies/`, not installed pkg | folded §2.2 + Q1 |
| B2 | coverage-as-gate can't reuse `check_policy_registry` (ScanContext-coupled, counts bootstrap) | folded §3.4 — extract pure `discover_implemented_policies()` |
| B3 | missing_structure_owner can't fire if golden has a `.` root catch-all | folded §2.2 |
| B4 | dogfooding row wrong: no-protocol → `dogfooding-protocol-missing` WARNING; target-missing → `dogfooding-protocol-target-missing` error | fixed §3.1 |
| B5 | waiver field is `expires`, not `expiry` | fixed §3.1 + §4 |
| B6 | **waiver SUPPRESSION does not exist** (`check_waivers` validates schema only; `provenance.py:23` "out of scope for now") — M3 can't test it | rewrote §4; **product gap → separate task** |
| S1 | document_set mutation can be pre-empted by config_sources | fixed §3.1 |
| S2 | config_sources severity dynamic — pin authoritative (error) vs supporting (warning) | fixed §3.1 |
| S3 | stale_wiki_claim trigger surface wider — pick one variant | fixed §3.1 |
| S4 | generated_wiki_drift only checks unit/roadmap claims; source-hash not a run_check finding | fixed §3.1 |
| S5 | dup pair fixture must spell out the exact module-set claim | note → M2 build |
| S6 | M9: assert shape, not byte-identical stdout | fixed §6 |

Nits: M8 missing from §1 diagram; rename remaining "expiry"→"expires"; English test method names.
All resolved or carried into the M2/M9 build tasks. Design is now SOUND TO BUILD after the §3.4
`discover_implemented_policies()` refactor lands as the M2 task's first sub-step.
```
