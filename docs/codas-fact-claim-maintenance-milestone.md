# Milestone direction — Fact & Claim maintenance (CodeGraph as a multi-language fact source)

Status: DIRECTION MARKER (not a committed plan). Authored 2026-06-22 from a design dialogue.
Owner: Codas Core. Companion to the Perception Model in `CONTEXT.md`.

This document sets the direction for the milestone AFTER the Python-only + Swift-thin-slice era:
let Codas govern multi-language repos by widening its FACT base, while the CLAIM layer (the part
no code-graph tool has) stays Codas's product. The central engineering question is the title:
**how does Codas maintain its OWN facts and claims** as the fact base grows and some facts start
coming from an external, non-deterministic provider.

## 1. The problems this milestone targets (stated by the product owner)

Three recurring agent failures Codas exists to fix:

1. **Reuse miss / reinventing wheels.** When an agent creates a new entity it fails to connect it
   to existing ones, so it re-implements what already exists.
2. **No global view / missed co-change.** An agent makes a local change and only edits that code,
   not the other parts that must change with it.
3. **Decisions don't reach the docs (MOST IMPORTANT).** A design decision changes the code but the
   PRD / design doc is never updated — the doc silently lies about the code.

## 2. The reframe — fact provider vs governance layer

```
CodeGraph (and tree-sitter, ctags, SCIP, …)   →   "what the code IS"      (FACTS)
Codas claim / coupling / ownership / gate      →   "what it MUST satisfy +  (GOVERNANCE)
                                                    does the doc still match"
```

- CodeGraph is a **fact provider**: multi-language symbols / imports / call-graph / impact, 100%
  local, no LLM, tree-sitter-based. It is a code graph — **it has no model of documents**, so it
  structurally cannot touch problem 3.
- Codas is the **governance layer**: it turns facts into reuse enforcement, co-change enforcement,
  ownership, and — uniquely — **code↔doc claims** (the bridge CodeGraph lacks).
- So Codas = *CodeGraph's facts + a doc-coupling/governance layer CodeGraph does not have.*
  CodeGraph does not replace Codas; it **widens Codas's fact base from Python-only to many
  languages**, so every Codas mechanism (duplicate, ownership, impact, code_anchor, fact_coupling)
  starts working on Swift / TS / Go / …

Leverage of CodeGraph on the three problems (be honest):

| problem | CodeGraph leverage |
| --- | --- |
| 2 — impact / co-change | **high** — its call graph *is* this |
| 1 — reuse | **medium** — gives multi-lang symbols (name/signature match), NOT semantic "same concept, different name" (that is `duplicate_concept`, still planned; neither tool catches it) |
| 3 — doc drift (most important) | **direct=low, indirect=high** — it cannot reach docs, but it widens the fact base the Codas claim layer resolves against, so doc↔code coupling extends to multi-language |

Key truth: **the engine for problem 3 is always Codas's claim layer. CodeGraph only widens the
languages it can cover.** Do not expect CodeGraph to solve problem 3 — it is structurally blind to
docs.

## 3. PART A — How Codas maintains its FACTS

A fact = a sound, observed statement about the code (a symbol exists; A imports B; A calls B).
Maintenance = how facts are produced, refreshed, trusted, and kept consistent as the source set
grows. Two properties govern everything:

- **Open-world (sound lower bound).** Static reading proves *existence*, never *absence*. "X is
  never called" is unprovable (dynamic/reflective/cross-language calls are invisible). So: **what a
  fact says is true; what facts DON'T say is UNKNOWN, not false.** Facts are a floor, not a ceiling.
  (Config is the opposite — closed-world, complete by declaration: not-in-structure.yml ⇒ truly
  unowned.)
- **Determinism.** A fact pipeline that feeds a *gate* or a *committed artifact* must be a pure,
  reproducible function of the governed inputs only.

### 3a. The maintenance fork (the real decision)

| | **Stateless re-derive** (Codas today) | **Stateful incremental** (CodeGraph-style) |
| --- | --- | --- |
| how | re-derive facts from current code at any moment; byte-compare committed artifacts | a persistent index (SQLite) advanced per commit; diff adjacent states |
| freshness | *verified after the fact* (`--verify` / drift policies) | *maintained during* the commit |
| needs the byte hash | yes (the reproducibility fingerprint) | no |
| state to corrupt | none | a live index that must never desync |
| robustness | **bypass-proof, history-agnostic, machine-agnostic** (any checkout self-verifies) | fragile to anything off the gate path: rebase, merge (two parents), `--no-verify`, second machine, second tool → silent desync |
| cost | re-derive each check | cheap per commit |

This fork was stress-tested in the dialogue and resolves to a **tiering**, not a winner:

- **Hash-bound / committed-fact tier → stateless re-derive, Codas-own deterministic extractors**
  (Python stdlib `ast` today; a thin tree-sitter Swift adapter if Swift facts must enter the gate).
  Small, controlled, reproducible. This is what the byte-identical inventory protects.
- **Advisory / multi-language tier → CodeGraph (or any external graph), never in the hash.** Fed to
  `impact`, reuse hints, and multi-language claim resolution. Open-world + tagged provenance;
  heuristic / cross-language edges stay advisory, never gate.

### 3b. What the byte hash is actually FOR (its necessary domain has shrunk)

The dialogue narrowed the hash to one residual job: **verifying that committed, derived artifacts
(AGENTS.md block, the wiki book, the CI workflow) still match the facts** — because AGENTS.md *must*
be committed (it is the injection carrier an agent reads), and a committed derived file must be
checkable for staleness, which needs deterministic rendering + a fingerprint.

But even that is mostly reducible:
- A renderer-only change does not change code meaning; whether it counts as "stale" is a design
  choice, and a wiki that tracks *content* need not re-commit on cosmetic re-render.
- Global-input changes (`structure.yml` / `policies.yml` → AGENTS.md content) are FEW and KNOWN →
  a small explicit rule set ("config X changed ⇒ regenerate doc Y") handles them without a global
  hash.
- The ONE irreducible place a rule set cannot be complete *in principle* is **code→doc propagation
  through the open-world call graph** (a lower bound, so "which docs are affected" is
  under-approximated). Full re-derivation is the only check independent of graph completeness.

→ Net: the hash is not a deep invariant; it is the **insurance premium for "no propagation rule set
to keep complete,"** and its irreducible value lives exactly in the open-world residual. A milestone
decision is whether that residual is worth the byte-identical tax, or is acceptable as advisory.
(Recorded as an open ADR — see §6.)

### 3c. Fact maintenance contract per tier (the rule to hold)

- A fact that **gates** or enters the **hash** MUST come from a deterministic, in-core extractor.
- A fact from an **external provider** (CodeGraph) is **advisory-only or diff-gate-only**, carries
  `provenance` + `resolution` tags, never enters the byte-identical inventory, and degrades to empty
  when the provider is absent (open-world: fewer facts, never a false denial).

## 4. PART B — How Codas maintains its CLAIMS

A claim = a statement in a hand-authored doc that references code (`defines: pay.py::charge`,
`calls: A→B`, a path/symbol span in a PRD). Claims are how a decision in prose is **anchored** to the
code it describes — and the mechanism for problem 3.

### 4a. The claim lifecycle (today)

```
author claim in a doc  →  verify each scan (resolve against current FACTS)
        →  code changes  →  claim no longer resolves = DRIFT
        →  detected by stale_claim / code_anchor / stale_wiki_claim (advisory)
        →  fact_coupling: a change to a watched symbol REQUIRES its companion doc path to
           co-change in the SAME commit  →  gate blocks if you changed code but not the PRD
        →  agent/human repairs the doc  →  claim resolves again
```

So Codas already turns "silently forgot to update the PRD" into "the gate blocks until the PRD is
updated." It does **detect + enforce co-change**; it does **not author** the fix.

### 4b. The two maintenance gaps this milestone must address

1. **Detection → repair (the problem-3 frontier).** Today Codas makes drift *visible* and *gates*
   it. The milestone question: should Codas *help repair* the claim — e.g. surface the exact PRD
   span that is now false and the new fact it must reflect, so the agent's fix is a targeted edit,
   not a re-read? (Repair stays agent/human-authored — §17 zero-LLM-core — but Codas can hand the
   agent a precise, fact-grounded repair target. This is the highest-value problem-3 work.)
2. **Multi-language claim trust.** When a claim resolves against CodeGraph facts (Swift/TS/…), the
   facts are open-world AND from a non-deterministic provider. So:
   - A claim that **gates** (fact_coupling co-change) must resolve against **in-core deterministic**
     facts → for Swift this means the thin tree-sitter adapter, NOT CodeGraph.
   - A claim that is **advisory** (code_anchor warning, reuse hint) may resolve against CodeGraph
     facts, tagged open-world, never gating on absence.
   - i.e. the **claim's enforcement tier must match its fact's trust tier.** A gate-claim may never
     depend on an advisory-only fact. This is the central invariant the milestone introduces.

### 4c. Reuse (problem 1) as a claim/fact interaction

Reuse enforcement is where fact and claim meet: at task start the preflight digest **injects reuse
candidates** (existing symbols near the agent's intent) and at commit `duplicate_implementation`
**gates** exact duplicates. CodeGraph widens the candidate pool to multi-language. The unsolved half
— "same concept, different name" — is semantic (`duplicate_concept`, planned); it needs a similarity
signal neither exact-name nor a call graph provides, and is a separate research line (LLM-judge as
advisory, never gating — §17).

## 5. Milestone scope (what to build, in order)

1. **`adapters/codegraph.py` — external multi-language fact adapter** (subprocess to the CodeGraph
   CLI; map its graph → `SymbolFact` / `ImportFact` / `CallFact` with `provenance`/`resolution`
   tags). Advisory tier only; never enters the inventory hash; degrades to empty when absent.
2. **Tier-tagged fact merge** in `ScanContext` (the additive-merge seam from the Swift design),
   keeping the deterministic in-core tier and the advisory CodeGraph tier separate and labeled.
3. **Multi-language claim resolution** — `code_anchor` (advisory) resolves against the widened fact
   base; `fact_coupling` (gate) resolves ONLY against in-core deterministic facts (the §4b
   invariant).
4. **`impact` over the widened graph** (problem 2), advisory + diff-gate co-change.
5. **Repair-target surfacing for drift** (problem 3) — the precise stale span + the fact it must
   reflect, injected to the agent. Highest product value; build last (needs 1–3).

This reshapes the current Swift thin-slice task: the hand-built tree-sitter Swift adapter remains the
**gate-grade, deterministic** path (step into the hash tier); CodeGraph is the **advisory,
multi-language** path. They serve different tiers and coexist — see
`.trellis/tasks/06-22-swift-extraction/design.md`.

## 6. Open decisions (carry into the milestone's design + codex review)

- **ADR: byte-identical hash vs diff-gate maintenance.** Keep stateless re-derive (bypass-proof,
  the hash tax) or move committed-artifact freshness to an explicit "global-input ⇒ regenerate"
  rule set, accepting the open-world code→doc residual as advisory? Decide per how dirty the real
  git workflow is (multi-worktree, multi-agent, rebases all argue for keeping stateless verify).
- **Determinism of CodeGraph output** (ordering, version, incremental-vs-fresh) — measured + a
  pinned version before ANY gate use; advisory use tolerates it.
- **CodeGraph as a runtime dependency** — Node tool, subprocess-only (cannot embed in Python; its
  pip-cousin tree-sitter-analyzer hard-deps `anthropic`/`numpy`/`mcp` and is rejected). Optional,
  graceful-degrade.
- **Cross-language heuristic edges** — surfaced in `impact` as tagged advisory; never gate (a wrong
  cross-language edge would falsely block a commit — worse than a missed hint).
- **duplicate_concept (semantic reuse)** — separate research; LLM-judge advisory only.
