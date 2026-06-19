# Codas Atlas Wiki

## Purpose

Codas is the first governed workspace for Codas itself. Until the `codas`
CLI can enforce the full policy set, this wiki records the canonical concepts
and source anchors that agents must read before implementation.

## Canonical Sources

- `docs/codas-design.html`: authoritative product and architecture design.
- `docs/codas-implementation-plan.html`: authoritative implementation architecture and module plan.
- `docs/codas-structure-map-schema.html`: authoritative Structure Map schema.
- `.codas/config.yml`: repo-local Codas bootstrap configuration.
- `.codas/policies.yml`: bootstrap policy set.
- `.codas/structure.yml`: authored Repository Structure claims.
- `.codas/program.yml`: authored Program Plan claims (project-level roadmap P0–P7).
- `.codas/documents.yml`: authored Document Role Manifest (Project Document Set: roles, paths, authority, owners, update triggers).
- `.codas/waivers.yml`: explicit waivers. Empty means no active waivers.
- `.trellis/workflow.md`: canonical development workflow.
- `.trellis/spec/codas/workflow/task-system.md`: Codas-specific Trellis task-system rules.
- `.trellis/tasks/**`: persisted task requirements, context and metadata.

## Concepts

- [Codas Product](concepts/codas-product.md)
- [Repository Structure](concepts/repository-structure.md)
- [Trellis Task System](concepts/trellis-task-system.md)

## Bootstrap Rule

Before editing this repository, an agent must identify the affected concept,
read the relevant canonical source, and report the bootstrap gate result:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
git status --short
```

## Authoring

The Atlas Wiki authoring contract lives at [CONTRACT.md](../../CONTRACT.md): what is
governed vs supporting, the `atlas:claims` grammar, and the `codas wiki` workflow.
Generated pages under `concepts/` are hand-authored; pages under `generated/` are
machine-rendered by `codas wiki --write` and must not be hand-edited.
