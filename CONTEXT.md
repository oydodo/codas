# Codas

Codas is a governance context for codebases maintained over time by coding agents. It reconciles repository facts with human-authored claims so agents and CI can make evidence-backed decisions about code changes.

## Product Layer

**Codas**:
Code Atlas System. A language-agnostic, agent-agnostic governance harness for codebases maintained long term by coding agents.
_Avoid_: Swift-only harness, prompt pack, one-agent plugin

**Codas Core**:
The agent-agnostic core that extracts facts, reconciles claims, runs policies, emits findings and manages waivers.
_Avoid_: Codex implementation, Claude Code implementation, hook script

**Atlas Inventory**:
The machine-readable repository index produced or consumed by Codas, including artifacts, symbols, modules, references, concepts, facts and claims.
_Avoid_: Wiki, truth source

**Artifact**:
Any repository entity Codas can reason about, such as source files, tests, configs, schemas, docs, specs and task files.

**Symbol**:
A language-level structure such as a class, struct, function, component, route, service, schema or command.

**Module**:
An architectural organization unit derived from packages, targets, namespaces, directories, services, frameworks or explicit structure claims.

**Concept**:
A business or architecture idea that can span files and modules, such as Auth, Composer, Billing, Chat Renderer or Model Provider.

## Fact Layer

**Fact**:
A verifiable observation Codas extracts from the repository.
_Avoid_: Truth, wiki fact, accepted claim

**Observed Fact**:
A Fact produced directly from repository evidence such as files, parser output, Git state, task files or document text.
_Avoid_: Raw truth, source of truth

**Claim**:
A statement authored in repository content about how the codebase should be understood or governed.
_Avoid_: Fact, rule, truth

**Governance Fact**:
A Claim accepted by Codas as a governance input after authority, evidence and conflict checks.
_Avoid_: Claim, wiki fact, opinion

**Evidence**:
The concrete repository evidence supporting a Fact or Claim, such as a file path, line number, symbol, AST node, document section, task record or Git state.
_Avoid_: Explanation without path, LLM rationale

**Conflict**:
A contradiction between Claims or Governance Facts about ownership, canonical placement, state, responsibility or allowed dependency direction.

**Drift** and **Staleness** (the change-governance 2×2):
Drift and staleness are **the same condition — an artifact inconsistent with the Facts it should reflect — found at two different times**, not two kinds of divergence. Two orthogonal axes:
- **Axis 1 — did this artifact change in the current diff?** changed / unchanged
- **Axis 2 — is it consistent with the Facts it should reflect?** consistent / inconsistent

|              | consistent        | inconsistent                          |
|--------------|-------------------|---------------------------------------|
| **unchanged**| quiescent (ok)    | **Staleness** (no diff to blame)      |
| **changed**  | normal (a clean update) | **Drift** (this change broke it) |

- **Drift** = changed + inconsistent. The change introduced (or failed to propagate) an inconsistency; **diff-attributable**, so it is caught at commit time by a diff-based detector (a co-change gate over the change + the fact-delta).
- **Staleness** = unchanged + inconsistent. The inconsistency exists with **no diff to attribute it to** — it was introduced in some past commit and never caught — so it is found only by **re-verifying the artifact against current Facts** (a state-based detector), on any run, even on a clean tree.

Because they are the same disease at two times, **both detector families are needed**: a diff-based gate blocks a bad change as it happens; a state-based check catches inconsistency that already slipped in. A `_drift`-suffixed policy name does **not** imply the change-axis — several state/staleness checks carry legacy `*_drift` names.
_Avoid_: treating "out of date" as one undifferentiated condition; assuming "inconsistent" is only ever a diff-time concern; reading a `*_drift` policy name as a diff-based check without verifying which axis it covers.

## Structure Layer

**Repository Structure**:
The intentional organization of files, directories, module boundaries, ownership and canonical placement inside a repository.
_Avoid_: File system, filesystem, folder layout when governance is meant

**Structure Map**:
The repo-local, verifiable carrier for Repository Structure claims. It describes structure units, ownership, canonical placement, dependency rules, deprecated paths and update obligations.
_Avoid_: Wiki page, informal directory notes

**Structure Unit**:
An addressable entry in the Structure Map, such as a directory, module, package, feature area, service or component group.

**Ownership**:
The declared owner of a Structure Unit, concept or capability. Ownership can refer to a module, team, role, canonical file or maintained boundary.

**Canonical Placement**:
The expected location for a kind of code, capability, component, configuration or documentation.

**Structural Drift**:
A mismatch between repository state and the Structure Map or accepted Governance Facts. (Despite the name, this is the general inconsistency: it surfaces as **Drift** when a commit introduced it — diff-attributable — or as **Staleness** when it is detected with no triggering diff. See the Drift/Staleness 2×2.)

**Orphan Artifact**:
An Artifact that exists without a clear reference, owner, task context, build path or documentation explanation.

**Duplicate Implementation**:
Multiple similar implementations of the same concept, capability or responsibility without an explicit canonical, variant or migration relationship.

## Orientation Layer

**Orientation Layer**:
A readable summary layer that helps agents and humans navigate repository facts and claims without becoming a source of facts.
_Avoid_: Truth source, knowledge base, fact store

**Atlas Wiki**:
The repo-local implementation of the Orientation Layer under `.codas/wiki`.
_Avoid_: Wiki fact, source of truth, canonical database

**Concept Index**:
An index that answers what a concept is, where it is implemented, which modules are related and which implementation is canonical.

**Decision Index**:
An index of important product, architecture and structure decisions that points to ADRs, PRDs, specs, tasks or code evidence.

**Grounding**:
Codas emitting verified Facts for an external author — a coding agent or an LLM-wiki generator — to consume: "Codas grounds it, an author renders it, Codas verifies it." The author writes prose or generated pages; Codas verifies their checkable Claims against Facts before any are accepted as Governance Facts. The correctness core stays deterministic and authors no prose itself.
_Avoid_: Codas writing prose, an embedded LLM in the correctness core

## Governance Layer

**Policy**:
An executable governance rule, such as forbidding orphan artifacts, requiring Structure Map updates, or checking whether a PRD/spec claim is still consistent with implementation Facts (as Drift at commit time, or Staleness at rest).

**Finding**:
A Policy result describing a problem or unresolved risk, including severity, evidence, reason and suggested fix.

**Waiver**:
An explicit exception to a Finding or Policy. A valid waiver must include reason, owner, scope and expiry condition.

**Gate**:
An enforcement checkpoint, such as agent preflight, pre-commit, pre-merge, CI, branch protection or human review.

**Receipt**:
A durable record of a Codas run or agent work session, including inputs, inventory version, policies run, findings and check result.

## Task Layer

**Task System**:
The external or repo-local workflow system Codas integrates with. This repository uses Trellis.

**Work Item**:
A concrete unit of change, such as a Trellis task, GitHub issue, Linear ticket or local markdown task.

**Trace**:
The chain connecting requirement, design, implementation, check results and structure updates.

**Context Pack**:
Task-specific context Codas prepares for an agent before work begins, including relevant concepts, read-first files, risks and required updates.

**Program Plan**:
A project-level implementation roadmap above individual tasks, defining phases, work items, dependencies, sequencing and exit criteria.
_Avoid_: Single task PRD, ad hoc todo list

**Project Document Set**:
The expected set of governance and planning documents for a repository, including each document's role, path, authority, owner and update triggers.
_Avoid_: Informal docs list, README-only convention

**Document Role**:
The responsibility a governance or planning document serves in the repository, independent of its concrete path, format or title.
_Avoid_: Filename, document title

**Document Role Manifest**:
The repo-local carrier for the Project Document Set. It maps document roles to concrete files and explains when each file must be updated.
_Avoid_: Constraint source list without semantics

## Role Layer

**Domain Role**:
An implementation-independent responsibility in the Codas domain, defined by purpose, inputs, outputs and acceptance criteria.
_Avoid_: Skill, subagent, hook, tool

**Role Integration**:
A platform-specific mapping that lets an agent, automation or human workflow perform a Domain Role.
_Avoid_: Domain role, core concept, mandatory agent type

**Structure Architect**:
A Domain Role responsible near project start for designing and bootstrapping the Repository Structure.
_Avoid_: File system designer, scaffolder

**Structure Steward**:
A Domain Role responsible during project execution for maintaining the Repository Structure and preventing structural inconsistency (both drift and staleness).
_Avoid_: Cleanup agent, ad hoc reviewer

**Orientation Curator**:
A Domain Role responsible for maintaining the Orientation Layer and Atlas Wiki so navigation follows repository changes without becoming a truth source.

**Policy Maintainer**:
A Domain Role responsible for maintaining policies, severity rules, waiver rules and gate behavior.

**Task Steward**:
A Domain Role responsible for maintaining task-system hygiene and Trace completeness across PRD, spec, implementation and checks.

**Document Steward**:
A Domain Role responsible for defining and maintaining the Project Document Set and Document Role Manifest. During bootstrap, the Structure Architect may perform this role.

## Relationships

- The repository is the source of **Observed Facts**; Codas reconciles **Claims** against those facts.
- A **Claim** can be observed as an **Observed Fact** without being accepted as a **Governance Fact**.
- A **Governance Fact** requires authority, evidence and conflict checks, and must not be accepted from wiki text alone.
- The **Atlas Inventory** is machine-readable; the **Atlas Wiki** is human-readable; neither should be treated as an unverified truth source.
- The **Atlas Wiki** implements the **Orientation Layer** and may contain **Claims**, but it does not produce **Facts** by itself.
- **Repository Structure** is a governed repository concern, not the operating system filesystem.
- **Structure Map** is the verifiable carrier for **Repository Structure** claims.
- **Structure Architect** and **Structure Steward** are **Domain Roles**, not built-in bindings to one agent product.
- **Program Plan** governs project-level sequencing; **Task System** governs individual work-item execution.
- **Project Document Set** defines which planning and governance documents a repo should have; **Document Role Manifest** binds **Document Roles** to files.
- A **Role Integration** may implement a **Domain Role** as a Codex skill, Claude Code subagent, hook workflow, CI check, GitHub Action or human reviewer checklist.
- Codas core defines **Domain Roles** and governance contracts; integrations map those contracts onto specific execution surfaces.
- The **Structure Architect** establishes the initial **Repository Structure**; the **Structure Steward** keeps it aligned as the codebase changes.
- The **Document Steward** establishes and maintains the document roles that keep design, implementation, roadmap, task and spec artifacts consistent (preventing both drift and staleness).
- The **Atlas Wiki** can orient agents inside the **Repository Structure**, but Codas must still verify structural claims against repository facts.

## Example Dialogue

> **Dev:** "The wiki says Composer's canonical owner is `src/ui/Composer.tsx`. Is that a **Fact**?"
> **Domain expert:** "The **Fact** is that the wiki says this. The ownership statement is a **Claim** until Codas verifies it and accepts it as a **Governance Fact**."

> **Dev:** "Can I use the **Atlas Wiki** as the source of truth for where new files go?"
> **Domain expert:** "Use it as the **Orientation Layer**. It can guide you to the relevant **Claims** and evidence, but Codas still verifies those claims against repository facts."

> **Dev:** "Is Structure Steward a Codex skill?"
> **Domain expert:** "No. **Structure Steward** is a **Domain Role**. A Codex skill can be one **Role Integration** that performs it."

## Flagged Ambiguities

- "fact" was used to mean both repository observation and accepted governance decision. Resolved: **Fact** means verifiable repository observation; accepted decisions are **Governance Facts**.
- "wiki" was used to mean both readable summary and authoritative knowledge source. Resolved: **Orientation Layer** is the domain concept; **Atlas Wiki** is its repo-local product surface.
- "file system" was used to mean repository organization rather than OS-level storage. Resolved: **Repository Structure** is the governed domain term.
- "skill", "subagent" and "hook" were used to describe what Structure roles are. Resolved: Structure roles are **Domain Roles**; platform-specific executions are **Role Integrations**.
- "source of truth" was too broad. Resolved: use **Observed Fact**, **Claim**, **Governance Fact** and **Evidence** instead.

## Concept Map

How the glossary terms wire together, end to end. Two axes split at the top — **change**
is cheap and language-agnostic (a content hash / diff); **consistency** is expensive and
per-language (an adapter must interpret bytes into Facts). The fact-delta bridges them.
Everything above the `no-LLM` line is deterministic; a human/LLM only authors Claims (judging
materiality once) and judges meaning Facts cannot reach.

```
                       ┌──────────────────────────────────────────────┐
   Repository  ──────► │ code(.py)  docs(.md)  Atlas Wiki  config(.yml) │
                       │ git HEAD ◄┄┄ commit history (baseline)         │
                       └──────────────────────────────────────────────┘
              ╱                                              ╲
   CHANGE axis (cheap, language-agnostic)         CONSISTENCY axis (costly, per-language)
   content hash / git diff                        ADAPTERS  ◄── §11 boundary ──
        │                                         python(ast) markdown wiki git trellis
        ▼                                         "interpret bytes -> Facts"
   changed_paths                                          │
   "which FILES moved"                                    ▼
        │                                        ScanContext  (one scan, memoized)
        │                                        = the seam: Policies consume Facts here,
        │                                          never import an adapter
        │                                                  │
        │                                                  ▼
        │                            ┌────────────── FACTS (observed) ──────────────┐
        │                            │ symbols  imports  calls(call-graph)           │
        │                            │ doc_claims  wiki_claims  Structure units  tasks│
        │                            └───────────────────────────────────────────────┘
        │                                                  │
        │              authored CLAIMS ───────────────── verify ──► GOVERNANCE FACTS
        │              (claims.yml: fact_couplings,                  (a Claim Codas
        │               duplicate_relationships)                     checked against Facts
        │                    ▲ human writes once: materiality        and accepted)
        ▼                    │                                       │
   fact_delta ◄── HEAD snapshot vs working snapshot (identity-key diff)
   "which FACTS moved"                                              │
        │                                                           ▼
        ▼                                                       POLICIES
   ┌─ DRIFT detector ─┐                          ┌─ STALENESS detectors (state) ──────┐
   │ fact_coupling    │                          │ policy_registry  generated_wiki_drift│
   │ (Δfact + changed │                          │ stale_claim  stale_wiki_claim        │
   │  -> co-change?)  │                          │ structure_drift                      │
   └────────┬─────────┘                          └──────────────────┬───────────────────┘
            │           both serve the change-governance 2×2         │
            │       ┌──────────────┬────────────────────────────┐
            └──────►│              │ consistent  │ inconsistent  │
                    │ unchanged    │ quiescent   │ STALENESS ◄───┘ (state detectors)
                    │ changed      │ normal      │ DRIFT ◄───────┐ fact_coupling
                    └──────────────┴─────────────┴───────────────┘
                                       │
                                       ▼
                                  FINDINGS ──► RECEIPTS (provenance: inventory_hash +
                                                          policy_version)

  ── no-LLM line ───────────────────────────────────────────────────────────────────
  Everything above is deterministic (stdlib ast, sorted, content-only, byte-identical).
  A human/LLM acts only at: (1) authoring a Claim/coupling (judging materiality once),
  (2) judging MEANING the deterministic Facts cannot reach. Neither enters the core.

  advisory (not gated): must_update_if_changed  — coarse "unit changed -> doc changed" hint.

  ┌┄ future: single-pass oracle -> incremental propagation engine (worklist) ┄┄┄┄┄┄┄┐
  ┊ a fact_delta propagates along edges (calls / imports / fact_couplings) to re-check  ┊
  ┊ reachable nodes; new inconsistencies enqueue; iterate to a fixpoint. Terminates by  ┊
  ┊ content-hash dedup; a recurring hash = an unsatisfiable contradiction (a Finding,   ┊
  ┊ not a loop). Enabler = the persistent fact-cache (only changed nodes recompute).    ┊
  ┊ codas impact <symbol> is the CLI face of one hop of this reachable set.             ┊
  └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
```

Reading the spine: **Repository** → (split: cheap **change** signal vs per-language
**consistency** extraction) → one scan yields **Facts** → Facts plus human-authored
**Claims** verify into **Governance Facts** → **Policies** evaluate them → the result lands
in the **Drift / Staleness 2×2** (Drift = changed + inconsistent, gated at commit; Staleness
= unchanged + inconsistent, caught on any run) → **Findings → Receipts**. Today this is a
single-pass oracle (a pure function of repository state); the dashed box is the planned
incremental propagation engine that the fact-delta, call-graph and fact-cache are being
built to enable.

## Perception Model (evolved — fact families, claim schema, TMS lineage)

The Concept Map above is the shipped single-pass spine. A 2026-06-20 critique generalized it
into the model Codas is evolving toward. Three changes: the change/consistency split becomes
an open set of **fact FAMILIES**, each either **OPEN-** or **CLOSED-world** — a static
call-graph is byte-identical and each emitted edge is SOUND, but the set is a lower BOUND
(absence ≠ denial: completeness over runtime behavior is undecidable, Rice), whereas a
config/declared family is read in full so its absence IS evidence; a claim reasoning from an
open-world family's *absence* inherits that lower-bound caveat. A **Claim** becomes a
structured object (subject, assertion, grain, verifier-class, evidence, world, lifecycle)
verified by
**projecting** its evidence onto the families it names (many-to-many, not containment); and
propagation becomes **bidirectional** (seeded by fact-delta ∪ claim-delta, so a
top-originating intent edit is governed too). The determinism boundary is a **policy choice**
("no non-deterministic verifier in the core"), not a law.

Lineage: Codas is a deterministic single-context **Truth-Maintenance System** (JTMS) — facts
justify claims, belief is a pure function of the justification network, retraction is
dependency-directed (= the worklist). Provenance lineage tracks which facts justify a claim; self-adjusting
computation (Adapton/Salsa) makes the relabel incremental; Toulmin/Pollock/AGM name the claim
slots. Full rationale + competitive positioning + the multi-language path live in the 06-20
perception-model decision record.

```
                    Repository  (raw substrate: files, history)
                      │ perceived by ▼        (FACT flows UP)
   ┌──────── FACT FAMILIES — open set; each OPEN- or CLOSED-world ─────────────────┐
   │ static-content │ structure/call │  diff    │ declared  │ [runtime] [external]  │
   │  hash ⟨CLOSED⟩  │  ast ⟨OPEN⟩    │changed_  │units⟨CLOSED⟩  (future)            │
   │  file           │  symbol·edge   │ paths    │  page     │  semantics: NO fact  │
   └───────┬──────────── emit FACTS (deterministic → inventory) ──────────┬─────────┘
           │                                                              │ semantics =
  ─────────┼──── §17 = "no NON-DETERMINISTIC verifier in core" (CHOICE) ──┼── claim-only
           ▼                                                              ▲
   ┌─ VERIFY = project a CLAIM's evidence onto the families it names ─┐   │ optional L3
   │   (MANY-TO-MANY, not a tree)                                     │◄──┤ GENERATOR:
   │   CLAIM = {subject, assertion, grain, verifier-class,            │   │ host agent /
   │            evidence[], world, lifecycle{hash, expiry}}           │   │ CodeWiki / none
   └───────────────────────────────┬─────────────────────────────────┘   │ → output = CLAIM
                                    ▼  outcome by verifier-class
   GOVERNANCE FACT (verified) │ FINDING (REBUT: fact contradicts) │ RESIDUE (UNDERCUT:
                              │                                   │ sensor can't reach;
                              │                                   │ evidence-only, stored
                              │  verdict = 2×2 (changed?×consistent?)  w/ hash+expiry)
                                    ▼
   PROPAGATION — BIDIRECTIONAL worklist: seed = fact-delta ∪ CLAIM-delta → re-verify → fixpoint
                                    ▼
                              RECEIPTS (provenance-pinned)
```

A claim outcome is one of three (the Pollock split): **GOVERNANCE FACT** (verified),
**FINDING** (*rebutted* — a fact contradicts the claim), or **RESIDUE** (*undercut* — the
claim rests on an open-world family's absence, so the sensor cannot confirm it; stored with
evidence and a re-checkable lifecycle, never reported as a violation). "Code is wrong" and
"I can't see well enough to judge" are different verdicts — the open-world invariant is what
keeps the second from being mis-reported as the first.

## Positioning — Karpathy's LLM-wiki framework (wiki pluggable; schema / authoring / maintenance enforced)

Recorded 2026-06-20 after a research+critique workflow (mapped Andrej Karpathy's "LLM-wiki /
docs-for-agents" model, FSoft-AI4Code CodeWiki, and Codas; synthesized; then adversarially
de-hyped). The cleanest external framing Codas has: locate it INSIDE Karpathy's framework.

**Karpathy's model = 4 load-bearing pieces over the raw repo** (raw sources are layer 0):
1. **wiki** — an LLM-authored, navigable knowledge artifact, so the agent does not re-derive
   from raw files each query ("compile once, maintain" = RAG-inversion).
2. **schema** — the human-owned contract (`AGENTS.md` / llms.txt) declaring how to read the
   repo and what is authoritative.
3. **authoring** — the convention of *writing the repo for an LLM reader* (push: the owner
   writes the entry points / menu; the agent does not reverse-engineer everything).
4. **maintenance** — the discipline of keeping the wiki/schema fresh as code evolves (a stale
   compiled artifact is worse than none).

In Karpathy's framing all four are **conventions** — practices a human is *supposed* to
follow. None are enforced. Codas's route is to make 2–4 enforceable and leave 1 pluggable.

**Codas's route inside the frame:**
- **Layer 1 (wiki) = PLUGGABLE, an explicit NON-GOAL to author.** Producing prose is the
  crowded, commoditized LLM battleground (DeepWiki / CodeWiki / host-agent give it away).
  Codas does not win there and does not try. The prose SOURCE is swappable: host-agent-direct
  (primary), CodeWiki (Block B, license-gated), or none. Codas touches this layer ONLY at the
  SEAM — it FEEDS the generator a fact-derived spine (the deterministic knowledge tree,
  `codas wiki --emit-tree`, schema `knowledge_tree/v1`) and CALIBRATES the output back to
  facts. It never authors the prose.
- **Layers 2–4 = where Codas wins, by turning each CONVENTION into an ENFORCED ARTIFACT**
  (the creed: process can't be enforced, artifacts can).
  - **2 schema →** `structure.yml` + `CONTRACT.md` + `codas schema` + the knowledge tree,
    with the schema's claims MACHINE-VERIFIED (live, not a hand-maintained doc that rots).
    [largely shipped]
  - **3 authoring →** inverted: author CLAIMS (checkable) instead of prose (hope). The
    deliverable changes from "write prose, trust it" to "write a claim, the machine checks
    it." [partly shipped]
  - **4 maintenance →** the killer, and shipped: drift gates (`fact_coupling` /
    `must_update_if_changed`: code changed without its claim source = error) + stale gates
    (`stale_claim` / `generated_wiki_drift`: a claim fell behind the facts = error). Karpathy
    says "maintain it"; Codas fails the build if you don't. [shipped]

One-line positioning: **Codas = Karpathy's framework with layers 2–4 promoted from convention
to enforced artifact, and the wiki layer left pluggable** — "the determinism / enforcement
layer UNDER `AGENTS.md`."

### 3-way comparison

| axis | Karpathy LLM-wiki | FSoft CodeWiki | Codas |
| --- | --- | --- | --- |
| altitude | interface convention (write source+docs FOR the agent) | post-hoc description (generate prose FROM the repo) | verification / governance substrate (verify claims AGAINST facts) |
| who authors knowledge | LLM writes the wiki; human owns schema | LLM writes the docs; deterministic graph only seeds | human/agent authors CLAIMS; Codas verifies, never writes prose |
| determinism | none (committed LLM prose, non-reproducible) | skeleton only (graph); clustering + prose non-deterministic | byte-identical, content-hashed, LLM-free CORE (load-bearing, CI-gated) |
| verification | none (lint = LLM-checks-LLM) | none on the prose (only the graph is sound) | machine-checked: claim ↔ code, declared ↔ implemented |
| completeness honesty | closed-world (implies "this is everything") | closed-world (confident overview) | OPEN-WORLD (facts = sound lower bound; absence ≠ denial) |
| direction | push (owner → agent) | pull (tool ← repo) | closed loop (facts ⇄ repo, verified) |

CodeWiki is an *instance of the wiki-generator category* Karpathy popularized — NOT an
implementation of his specific model: different lineage (a DeepWiki competitor), and it covers
only piece 1 (its least-trustworthy, LLM-author slice), dropping his schema / authoring /
maintenance pieces. Codas does the opposite — the three pieces nobody else enforces.

### Honest caveats (the critic's corrections — do not oversell)
- **Shipped vs planned.** Codas today enforces the FLOOR (schema + maintenance, layers 2 & 4).
  The richness that makes the wiki layer *immediately useful* (the W3 semantic judge +
  calibration, the layer-1 seam) is **unbuilt**, and extraction is **Python-first**.
- **W3 does only the SEAM, and the trust TAGS must be deterministic.** The judge FEEDS
  (fact-derived spine) + CALIBRATES (snap claims to facts → CONFIRMED / UNCONFIRMED /
  SEMANTIC). The tags must be assigned by a DETERMINISTIC fact-match, not by the LLM
  self-rating its confidence — else LLM-checks-LLM re-enters at the tagging boundary. Only the
  SEMANTIC residue (no fact exists) is irreducibly LLM. Output is suggestion-only, never
  committed (preserves byte-identity), and never upgrades a claim past the facts.
- **Authoring tax (layer 3).** Codas-grade verification needs a human/agent to AUTHOR a
  checkable claim — more labor than "write `AGENTS.md` and let an LLM review," which connects
  to the project's own #1 risk (unproven demand). Soundness ≠ adoption.
- **Layer-4 blind spot.** The maintenance gates catch directions expressible as a fact-delta
  or a structured-claim-vs-fact check. They do NOT catch doc→code drift (a stale spec the
  agent FOLLOWS) or free-prose staleness unless the prose is anchored to facts — Codas
  verifies the *less dangerous* direction.
- **Real nearest competitor = SonarQube (Architecture-as-Code), not these two prose
  generators.** Against it Codas's differentiation is free / lightweight / agent-native /
  byte-identical — NOT "has verification at all." Chasing the full wiki richness spends Codas's
  actual moat (the lightweight, pyyaml-only, serverless CLI under `AGENTS.md`), so layers 1 /
  multi-language extraction / judge stay opt-in or unbuilt by design.

Full maps + synthesis + critique live in the 2026-06-20 Karpathy-framework positioning task
ledger. Companion to the perception-model decision record above.
