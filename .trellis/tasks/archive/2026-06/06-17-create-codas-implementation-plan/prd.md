# Create Codas Implementation Plan

## Problem

Codas has a formal product/design direction, but implementation still needs a
concrete architecture and module breakdown. Without an implementation plan,
future agents may start with hooks, wiki generation or Swift-specific checks
before the core fact/claim/policy model exists.

## Goal

Create a formal HTML implementation plan that defines the Codas architecture,
module boundaries, data flow, implementation phases and acceptance criteria.

## Requirements

- Produce a self-contained HTML document under `docs/`.
- Define Codas' architecture around repo facts, claims, policies, findings and
  receipts.
- Clearly distinguish core systems from adapters, hooks, wiki and agent
  integrations.
- Include proposed package layout and module ownership.
- Include implementation phases from P0 migration through hooks/MCP.
- Include what is explicitly out of scope for the first slice.
- Register the plan as a Codas authoritative source and wiki canonical source.

## Acceptance Criteria

- `docs/codas-implementation-plan.html` exists.
- `.codas/config.yml` references the implementation plan.
- `.codas/wiki/index.md` references the implementation plan.
- Trellis task context validates.
- Bootstrap gate passes.
