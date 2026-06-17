# Grill Codas Domain Terminology

## Problem

Codas has several closely related terms: Fact, Claim, Governance Fact, Wiki,
Inventory, Policy and Finding. If these are not sharpened, future agents may
build features against ambiguous language.

## Goal

Stress-test Codas terminology one decision at a time and update `CONTEXT.md`
as terms are resolved.

## Requirements

- Ask one terminology/design question at a time.
- Record resolved domain language in root `CONTEXT.md`.
- Do not add ADRs unless a decision is hard to reverse, surprising and based
  on a real trade-off.
- Keep terms implementation-independent where possible.

## Acceptance Criteria

- `CONTEXT.md` exists once the first term is resolved.
- Resolved terms include Fact, Claim and Governance Fact.
- Resolved terms include Domain Role and Role Integration.
- Resolved terms include Repository Structure, Structure Architect and
  Structure Steward.
- Resolved terms include the product, fact, structure, orientation,
  governance, task and role layers.
- `docs/codas-design.html` and `docs/codas-implementation-plan.html` reflect
  the accepted terminology at a product and implementation-plan level.
- Trellis task context validates before the task is archived.
