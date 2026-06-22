# Per-turn injection: codas status + check-on-return hooks (gap 3)

## Goal

Close hole 3 (the last injection hole): the agent only gets governance at SessionStart (once),
so in a long session it forgets the ownership map / reuse candidates and writes a duplicate in
the wrong place — exactly the UNGATEABLE classes the commit gate is silent on. This task SHIFTS
THE FEEDBACK LEFT: right after code changes, surface "this file is unowned / under a deprecated
path / you defined a symbol that already exists elsewhere" to the agent so it self-corrects
BEFORE commit — turning the commit-time gate into edit/return-time feedback.

Design was reached via a grill-me interview; see design.md for the resolved decision tree and the
two VERIFIED Claude-hook facts that shaped it.

## Requirements

- R1 — NEW `codas status [path]` command (neutral, in `app/`): derives changed files from the git
  working-tree diff (reuse `ScanContext.changed_paths()`), runs the CHEAP policy SUBSET only —
  `check_missing_structure_owner`, `check_deprecated_path_used`, `check_duplicate_symbol` — and
  FILTERS findings to the changed files (or the given `path`). Reuses the real policy functions
  (no new check logic → no divergence from the gate); ScanContext laziness keeps it ~100ms (it
  never triggers the expensive cross-file resolution the gate's dependency_direction /
  duplicate_implementation / fact_coupling need). `--json` for the hook.
- R2 — Output is COMPACT + FACTUAL: e.g. "src/x.py: symbol `foo` also defined in src/y.py:42";
  "src/z.py: not owned by any Structure unit". Empty when clean. (Factual phrasing, NOT imperative
  — Claude's prompt-injection defense flags out-of-band system commands; verified.)
- R3 — A thin platform shim (integrations/claude) renders/installs project-level
  `.claude/settings.json` hooks that run `codas status` and wrap its findings as
  `hookSpecificOutput.additionalContext` (empty → no injection). Matchers:
  `SubagentStop` + `PostToolUse:Agent|Task` (CHECK-ON-RETURN — the MAIN path, fires when a
  delegation returns, injects the MAIN agent) and `PostToolUse:Edit|Write|MultiEdit` (bonus —
  the main agent's own edits). All inject the MAIN agent.
- R4 — UNIVERSAL by construction: because `codas status` diffs GIT (not the tool event), it
  catches changes made by ANY worker — a Claude subagent, a codex/tmux worker, or a human —
  since the check runs at the return boundary in the main agent (which IS in the hook system).
- R5 — §11/§17: `codas status` neutral in `app/` (reuses policies, no LLM, no judgment); the hook
  is a thin "run codas, emit additionalContext" shim in `integrations/`. Determinism: the per-run
  output is deterministic for a given tree; git volatility is fine (advisory, never in the hash).
  check 0; inventory byte-identical; suite green.

## Acceptance Criteria

- [ ] `codas status` on a repo with a freshly-changed unowned/deprecated/duplicate-symbol file
      reports it (filtered to changed files); clean tree → empty; ~100ms (no full resolution).
- [ ] `codas status --json` emits a shape the shim turns into `additionalContext`.
- [ ] `codas hooks --install` adds the check-on-return + per-edit hooks (marker-guarded,
      idempotent, foreign-safe) and records them in `.install-state.json`; doctor reports them
      (extends the 1/4 diagnostics).
- [ ] check 0; inventory byte-identical 2x; wiki/agents --verify clean; suite green; §11/§17 clean.

## Out of scope (deferred)

- Phase 2 "only-NEWLY-introduced collision" (before/after symbol diff). MVP = "collide → warn"
  scoped to the changed file (decided: simple, low noise since scoped). Noted in design.
- Per-subagent FRONTMATTER hooks (would let a Claude subagent self-correct mid-task) — the user's
  workers are codex (no frontmatter), so check-on-return covers them; frontmatter is a later add.
- Codex/Cursor platform shims for `codas status` (Codex has its own hooks). Claude-only MVP.
- Resolution-dependent checks per-turn (dependency_direction, duplicate_implementation) — too slow
  (~1.8s full check); they stay commit/CI-only.

## Notes

- Gate-adjacent? `codas status` only READS + reuses existing policies (no new gate, no scan/hash
  change); the hooks are advisory (never block — the commit gate stays the enforcer). Lighter than
  1/4, but still do an adversarial DESIGN review of design.md before building (codex MCP unusable
  -> Claude-native), then IMPL review.
- Builds on the shipped injection stack: [[codas-hook-injection]]. Reuses `ScanContext.changed_paths`
  (the digest's git-fact source) + the install-state contract + doctor (1/4).
