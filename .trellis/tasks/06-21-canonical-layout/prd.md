# Paradigm-constraint onboarding — Codas governs ARCHITECTURE, not directory layout

> REFRAMED 2026-06-22 (architect decision). This task was "opinionated canonical LAYOUT +
> scaffolding". That framing is REJECTED: scaffolding an opinionated directory layout
> (src/ docs/ tests/) is domain-blind, taste-imposing, and violates screaming architecture.
> The real feature is: Codas helps a repo DECLARE its architecture paradigm (as dependency
> constraints) and ENFORCES it — the project owns naming, the paradigm owns the skeleton.
> This is an EPIC (decision record + design + sub-task breakdown), not a single PR.

## Status: PLANNING (design fixed; sub-tasks not started). Gate-adjacent pieces need DESIGN review.

## Why (the onboarding gap)

`codas init` today scaffolds an EMPTY `.codas/` skeleton (single root catch-all unit). The
biggest cross-repo friction is empty `.codas/` → real governance. Codas's core (owner): assist
agentic coding · avoid duplication · follow best practices · honor design principles (MVC / DDD /
clean-arch / hexagonal / screaming). So onboarding must let a repo express + enforce a known
PARADIGM with near-zero ceremony — without Codas imposing a layout or taste.

## Decision record (architect, 2026-06-22; basis = 4-lens workflow wf_530b46c4-380)

1. **A preset encodes the PARADIGM CONSTRAINT (roles + `must_not_depend_on`), NOT directory
   names.** Paradigm owns the skeleton; project owns the naming. Carrier already exists
   (`structure.yml` `must_not_depend_on` + gated `dependency_direction`) → no new gate to express it.
2. **UNIT = BOUNDED CONTEXT (vertical), layers NESTED inside it — NOT top-level layers.**
   `_owning_unit_of` resolves by PATH PREFIX → a unit must be a contiguous subtree. A context
   (`orders/`) spans all layers and IS contiguous; a top-level `domain/` layer is the anti-screaming,
   technical decomposition. So the preset is a per-context STAMP: `orders/domain` ¬dep
   `orders/adapters`, replicated under each context. longest-prefix gates it with zero new mechanism.
   The path-prefix constraint is a COMPASS (it forces the screaming-correct shape), not a limitation.
3. **`--paradigm` is OPT-IN, planned-by-default; default is `none`/flat.** Role units seeded
   `status: planned` (so `structure_drift`, a gated error on absent `active` paths, does NOT fire on
   turn 1). A role arms (`planned`→`active`, its dep rule starts enforcing) only when mapped to a
   REAL existing directory. Default `none` = today's minimal skeleton.
4. **avoid-duplicate is the FREE day-1 value, DECOUPLED from paradigm.** `duplicate_implementation`
   (SCOPE_PREFIX `src/`) self-activates on any `src/` tree, zero roles/paradigm. Do NOT market
   "avoid-dup + dep-hygiene" as one init deliverable; dep-hygiene is a LATENT contract that arms
   post-mapping.
5. **ECOSYSTEM HONESTY is a hard requirement, not a nice-to-have.** The gate's import resolver is
   PYTHON-ONLY (`adapters/callgraph.py` + `python_parse.py`). On a non-Python repo a paradigm preset
   writes rules + a green gate that enforces NOTHING while AGENTS.md claims governance = manufactured
   false confidence (worse than no preset). init MUST detect the ecosystem and, without a resolver,
   write the preset ADVISORY-only + say so in CLI output AND the injected AGENTS.md. Each preset
   carries an `enforceable_for` tag.
6. **NEW differentiated gate = CROSS-CONTEXT PUBLISHED-INTERFACE.** Cross-context imports must go
   through one declared published-interface path per context; everything else is `must_not_depend_on`.
   Decidable, gateable, the real bounded-context invariant — more valuable than another layer check.
7. **role→path mapping = Nx TAGS model** (role carried by `unit_id`, naming by `path`). For existing
   repos, PROPOSE bindings from IMPORT-GRAPH coupling clusters (NOT directory-name sniffing — names =
   intent, not compliance; name-sniffing a paradigm is itself a §17 violation). Show the violations a
   binding WOULD raise BEFORE arming (informed consent). Map LAZILY when files appear.
8. **WHITE-SPACE = the AGENTIC angle.** Declare-then-enforce dep rules is COMMODITY (import-linter,
   ArchUnit, dependency-cruiser, Nx all do it, none scaffold). Codas's edge is machine-queryable atlas
   + AGENTS.md injection + preflight reuse digest feeding the agent — NULLIFIED if the gate under the
   injection is mute (hence #5). Onboarding narrative sells the agentic angle, not dep enforcement.

## §17 / determinism discipline

- A preset is curated deterministic DATA (YAML: role-unit ids + `must_not_depend_on` edges + nested
  layer roles + `canonical_placement` prose templates + `enforceable_for`); adopting it is a USER
  DECLARATION, not inference. Built-in tuple + user `.codas/presets/` + community (eslint
  shareable-config model). Overridable lazy defaults.
- init WRITES only declarations the user adopts; it never invents repo facts. Paradigm detection /
  cluster-suggestion is host-agent (§17-external) → PROPOSE text the user confirms; only the confirmed
  declaration is written + gated. Sniffing never enters the deterministic core.
- Two-layer split: GATE = (a) intra-context layer direction (b) cross-context published-interface —
  both decidable once contexts are DECLARED. INJECTION = which contexts exist + naming + the proposed
  mapping — judgement, agent-assisted. NB dep-hygiene is parasitic on the mapping (it is only as good
  as the declared paths); avoid-dup is pure-gate-free.

> MECHANISM CORRECTION (2026-06-22, verified `app/check.py:61-79`): `run_check` runs EVERY policy
> UNCONDITIONALLY; `policies.yml` does NOT gate which run nor override severity (each emits its own).
> It feeds only `dogfooding` + `policy_registry` (whose "implemented" set is `check_*` under
> `src/codas/policies/`, absent on a consumer → 0-vs-0 → passes). ⇒ `duplicate_*` / `dependency_direction`
> ALREADY run on ANY `.codas/` repo — `policies: {}` is the correct consumer default, there is NOTHING
> to "enable". The S1/S2 "policy enablement" idea below was a FALSE premise; struck. A paradigm preset
> works by JUST writing structure units with `must_not_depend_on` (S3) — `dependency_direction` enforces
> them with no enablement step. The epic SHRINKS accordingly.

## Sub-task breakdown (implementation sequence)

- **S1 — packaging (W8a, PREREQUISITE). ✅ SHIPPED `961a029`+`3f00e94`.** Broadened `requires-python`
  to `>=3.9` (verified) + README `## Install` quickstart; pip-install on 3.9 + console script (no
  `PYTHONPATH`) verified; check 0 / byte-identical / 563 tests. (Dropped the "init writes policy
  enablement" item — false premise per the correction above.)
- **S2 — honest framing only (NO code; was "avoid-dup decouple + policy enablement").** avoid-dup +
  the gate are ALREADY delivered by `codas init` alone (policies run unconditionally). S2 reduces to
  DOCS: state that `codas init` immediately gates duplicate top-level symbols under `src/` (the free
  day-1 value) and that `policies: {}` is the consumer's own (empty) registry, not a disable switch.
  Trivial; possibly fold into S3 docs.
- **S3 — paradigm preset MECHANISM (data only, reuses `dependency_direction`).** `--paradigm X` opt-in;
  preset = context-shaped role units (`planned`) + nested layer roles + `must_not_depend_on` +
  `canonical_placement` templates + `enforceable_for`; built-in few + user + community loader;
  ecosystem-honest advisory fallback. Dogfood: this repo's own `.codas` IS a hexagonal preset
  (codas-app/policies/core declare `must_not_depend_on: codas-adapters`) → first fixture + sample. Medium.
- **S4 — role→path mapping + existing-repo suggest.** Nx-tags mapping writes `unit.path` + flips
  `planned`→`active` against a real dir; existing repo: import-cluster suggestion (reuse
  `ScanContext.imports`), show would-be violations before arming, lazy bind. Medium-large.
- **S5 — GATE: cross-context published-interface policy.** New gated policy (#6). gate-adjacent →
  adversarial DESIGN review FIRST. Large.
- **S6 — GATE: role-membership / catch-all handling.** When a paradigm is active, "code outside the
  declared roles = finding" — needs dropping/neutralizing the root catch-all OR a new role_placement
  policy (today `missing_structure_owner` never fires with a root unit present, so the placement layer
  has no teeth). gate-adjacent → DESIGN review FIRST. Large.

Dependencies: S1 → S2 → S3 → S4; S5/S6 need S3 (context units exist), independent of S4. S5 before
S6 (published-interface is the higher-value tooth).

## Acceptance (epic-level)

- [ ] `codas init` (no paradigm) → minimal skeleton + avoid-dup live + policy enablement; check 0.
- [ ] `codas init --paradigm <ctx-preset>` seeds `planned` context+layer units; first `check` is
      GREEN (no structure_drift on planned), and INERT until mapped (documented, not silently sold).
- [ ] mapping a role to a real dir arms its dep rule; a real intra-context / cross-context violation
      is caught; non-Python repo → preset advisory-only + CLI + AGENTS.md SAY enforcement is off.
- [ ] presets are overridable data (built-in + user + community); a custom paradigm is a data file.
- [ ] every gate-adjacent sub-task (S5, S6) passed an adversarial DESIGN review before code.
- [ ] check 0; inventory byte-identical; agents/wiki --verify clean; suite green.

## Notes / open

- Rejected: scaffold a directory layout; top-level layer skeleton (anti-screaming, can't express
  contexts); directory-name sniffing; auto-imposing a sniffed paradigm.
- Neighbor `06-21-scope-exclude-knob` (exclude lever / hash-scope decouple) interacts with S4's
  root tightening — reconcile when S4/S6 are picked up.
- Full reasoning + the 5 code-verified false-claims in memory [[codas-ship-positioning]].
