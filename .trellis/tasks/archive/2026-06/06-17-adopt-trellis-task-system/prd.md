# Adopt Trellis as Codas Task System

## Problem

Codas is designed to govern repositories maintained by coding agents, but its
own implementation work must also persist task intent and decisions outside of
chat. Without a repo-local task system, future agents can miss the current
objective, duplicate work or forget to update Codas claims.

## Goal

Use Trellis as the task system for the Codas project.

## Requirements

- Initialize Trellis in this repository using the official Trellis structure.
- Treat `.trellis/workflow.md`, `.trellis/config.yaml`, `.trellis/spec/**` and
  `.trellis/tasks/**` as Codas constraint sources.
- Add a Codas-specific Trellis spec that explains how Trellis and Codas relate.
- Record this adoption work as a Trellis task.
- Update Codas design, wiki and README claims so future agents know Trellis is
  the canonical task system.
- Preserve the Codas boundary: Trellis manages workflow/tasks, while Codas
  manages atlas, policy gates, wiki, waivers and constraint conflicts.

## Non-Goals

- Do not migrate the existing prototype into the final `codas` CLI in this task.
- Do not require agent-specific Trellis skills to be installed before Trellis
  can be used as the task system.
- Do not make Trellis the architecture inventory or policy engine.

## Acceptance Criteria

- `.trellis/` exists and contains official workflow, config, scripts, specs and
  task structure.
- `.trellis/spec/codas/workflow/task-system.md` defines Trellis as Codas' canonical task
  system.
- `.codas/config.yml` enables Trellis as the workflow adapter and includes
  Trellis files as constraint sources.
- Codas design and wiki mention Trellis as the task fact source for this repo.
- Bootstrap gate passes.
