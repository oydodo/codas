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

**Drift** (change-triggered) and **Staleness** (state-based):
Two ways a Claim diverges from the Facts. **Drift** is a Claim source diverging because a change was not propagated — detected at the moment of change (diff-based). **Staleness** is a Claim's content falling behind current Facts with no single trigger — detected by re-verifying the Claim against Facts at any time. Codas must catch both.
_Avoid_: treating "out of date" as one undifferentiated condition

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
The repository state drifting away from the Structure Map or accepted Governance Facts.

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
An executable governance rule, such as forbidding orphan artifacts, requiring Structure Map updates, or checking PRD/spec implementation drift.

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
A Domain Role responsible during project execution for maintaining the Repository Structure and preventing structure drift.
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
- The **Document Steward** establishes and maintains the document roles that keep design, implementation, roadmap, task and spec artifacts from drifting.
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
