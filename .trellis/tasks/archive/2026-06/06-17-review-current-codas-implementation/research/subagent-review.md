# Subagent Review: Current Codas Implementation

Date: 2026-06-17
Reviewer: subagent `019ed4df-1059-7bb2-861f-f04846fd09e6`
Mode: read-only review

## Result

No P0/blocker was found.

## Findings

### P1: Core implementation still contains Swift/Ciri-specific assumptions

The design says Codas must be agent-agnostic and language-agnostic at the core
layer. The current Python implementation is still the original harness-guard
prototype and has Swift/iOS/Ciri assumptions in core paths.

Evidence:

- `docs/codas-design.html`
- `src/harness_guard/checks.py`
- `pyproject.toml`

Impact:

- Future agents may extend the prototype as if it were Codas core.
- Swift/XcodeGen/Ciri checks need to move behind adapters before the core model
  can be considered Codas.

### P1: Trellis task context files are not fully included in Codas task globs

Trellis and README define `implement.jsonl` and `check.jsonl` as persisted task
context, but `.codas/config.yml` currently tracks `task.json` and `prd.md`
only in `workflow.task_globs`.

Evidence:

- `docs/codas-design.html`
- `README.md`
- `.codas/config.yml`

Impact:

- Codas' Trellis workflow adapter would miss implementation/check context as
  task facts.

### P1: Bootstrap gate does not yet check Codas authoritative sources

`.codas/config.yml` declares Codas design/config/wiki/Trellis files as
authoritative or supporting sources. The existing `harness-guard` code still
checks the older Swift/Trellis/Ciri-oriented paths and does not validate the
new Codas sources.

Evidence:

- `.codas/config.yml`
- `src/harness_guard/checks.py`

Impact:

- A clean prototype check does not prove Codas dogfooding coverage.
- The first Codas self-check must read `.codas/config.yml` and enforce those
  declared sources.

### P2: Trellis start/current-task state does not change task status

`task.py start` sets `.trellis/.current-task` but leaves `task.json.status` as
`planning`.

Evidence:

- `.trellis/scripts/task.py`
- `.trellis/tasks/06-17-review-current-codas-implementation/task.json`

Impact:

- Future agents may see a current task that still appears to be in planning.
- This should be treated as Trellis adapter nuance or patched locally if it
  causes repeated workflow confusion.

### P2: Dogfooding protocol link points to a missing HTML fragment id

`.codas/config.yml` points to `docs/codas-design.html#dogfooding-protocol`, but
the HTML heading currently does not define that id.

Evidence:

- `.codas/config.yml`
- `docs/codas-design.html`

Impact:

- Agent or browser links cannot reliably jump to the dogfooding section.

### P2: Prototype package and CLI naming still point to harness-guard

The formal design defines `codas` as the product/CLI direction, but the Python
package and console script still expose `harness-guard`.

Evidence:

- `pyproject.toml`
- `README.md`
- `docs/codas-design.html`

Impact:

- This is expected during migration, but it is a real risk for future agents
  choosing where to extend behavior.

## Verification

The main agent verified the review setup with:

```bash
python3 ./.trellis/scripts/task.py validate 06-17-review-current-codas-implementation
PYTHONPATH=src python3 -m unittest discover -s tests
python3 ./.trellis/scripts/get_context.py --mode packages
```

Results:

- Trellis task context validation passed.
- Unit tests passed: 4 tests OK.
- Trellis recognizes `codas` as the default package with `workflow` spec layer.

## Recommended Next Step

Do a P0 migration slice:

- Add a `codas` package/CLI shell while preserving compatibility with the
  prototype command.
- Move Swift/Ciri-specific checks behind an adapter boundary.
- Make the first Codas self-check read `.codas/config.yml` and include Trellis
  `implement.jsonl` / `check.jsonl` as workflow facts.
