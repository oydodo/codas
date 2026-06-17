# Codas Product

## Canonical Definition

Codas is a Code Atlas System for coding agents: it maps a repository into
verifiable facts, gives agents task-specific architectural context, and blocks
changes that introduce duplicate implementations, orphan artifacts, stale
claims or unresolved constraint conflicts.

Evidence:

- `docs/codas-design.html`
- `.codas/config.yml`

## Scope

Codas applies to any codebase maintained long-term by coding agents. It is
agent-agnostic and language-agnostic at the core layer.

Evidence:

- `docs/codas-design.html`

## Current Implementation State

The current implementation is the P0 `codas` CLI core and self-check path.
Legacy `harness_guard` prototype code has been removed. Future Swift, Ciri or
XcodeGen behavior must be implemented through adapters, not the core model.

Evidence:

- `src/codas/`
- `scripts/codas`
- `docs/codas-design.html`
- `docs/codas-implementation-plan.html`
- `docs/codas-structure-map-schema.html`

## Workflow System

Codas uses Trellis as its project task system. Trellis stores durable task
intent and context; Codas consumes it as workflow facts through the Trellis
adapter.

Evidence:

- `.trellis/workflow.md`
- `.trellis/spec/codas/workflow/task-system.md`
- `.codas/config.yml`

## Duplicate Risks

- Do not implement Codas as only a Codex skill.
- Do not implement Codas as only a Claude Code hook.
- Do not keep Swift/XcodeGen checks in the core layer after adapter extraction.
- Do not let generated wiki pages become higher authority than facts and
  explicit constraint sources.
- Do not treat Trellis as a substitute for Codas inventory or policy gates.

## Required Synchronization

When changing command shape, policy semantics, repo-local state, adapter
boundaries, data model or enforcement rules, update:

- `docs/codas-design.html`
- `docs/codas-structure-map-schema.html`
- `.codas/structure.yml`
- `.codas/wiki/index.md` or this concept page when navigation changes
- `.codas/policies.yml` when policy behavior changes
