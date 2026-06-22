# Design — Per-turn injection (gap 3)

Reached via a grill-me interview. This records the resolved decision tree, the two VERIFIED
Claude-hook facts, and the concrete change map. Build after an adversarial DESIGN review.

## 0. Resolved decision tree (grill-me)

| Decision | Resolution | Why |
|---|---|---|
| The job | CATCH ERRORS at edit/return time (incl. duplicate-symbol), not just "remind" | the digest already covers reminders (pull); the unique value is JIT error-catching on the UNGATEABLE classes |
| Cost / caching | ~100ms, NO cache | MEASURED on this repo: full check 1783ms, but symbol-only extraction 97ms, git changed-paths 19ms. The 1.8s is RESOLUTION (calls/imports); duplicate-NAME needs only symbols. The deferred fact-cache dragon does NOT bite. |
| Engine | REUSE the cheap policy SUBSET, filter to changed files | `check_missing_structure_owner` + `check_deprecated_path_used` + `check_duplicate_symbol` are individually callable; ScanContext is LAZY so calling only these computes only cheap facts. No new logic → no divergence from the gate. |
| Trigger | CHECK-ON-RETURN (main) + per-edit (bonus) | see §1 — project hooks do NOT reach subagents |
| Universality | diff GIT, not the tool event | catches Claude-subagent / codex / tmux / human edits alike, because the check runs at the main-agent return boundary |
| Noise | "collide → warn", scoped to the changed file | simplest; low noise because scoped; "only-newly-introduced" is a deferred refinement |
| Strength | ADVISE, never block | injection advises; the commit gate enforces (two-tier). PostToolUse is post-edit anyway. |
| Phrasing | FACTUAL statements, not imperatives | verified: Claude's prompt-injection defense flags out-of-band system commands |

## 1. VERIFIED Claude-hook facts (claude-code-guide, official docs) — the crux

- **Project `.claude/settings.json` hooks do NOT apply inside subagents.** A subagent's Edit/Write
  does NOT fire a project-level `PostToolUse`. To reach a subagent you'd need a hook in the
  subagent's FRONTMATTER (injects THAT subagent) — but the user's workers are codex (no
  frontmatter), so this path is dead for them.
- **`SubagentStop` (project-level) fires when a subagent completes and injects the MAIN agent.**
- **`PostToolUse` matcher `Agent`/`Task` fires when the Agent/Task tool returns, injecting the MAIN
  agent.** Caveat: the event gives the agent RESULT (summary + id), NOT the file list → derive
  changes from git (which `codas status` does anyway).
- **`PostToolUse` matcher `Edit|Write|MultiEdit`** fires + injects for the MAIN agent's OWN edits.
- Injection mechanism (all of the above): exit 0 + JSON `{"hookSpecificOutput": {"additionalContext": "..."}}`;
  empty/no output → no injection. `additionalContext` enters the receiving agent's context.

=> The MAIN path is CHECK-ON-RETURN (SubagentStop + PostToolUse:Agent), because that is what
reaches the main agent after a delegated/codex edit. Per-edit (PostToolUse:Edit) is a bonus for
direct main-agent editing. All three are project-level and inject the MAIN agent; the main agent
then fixes or re-delegates.

## 2. `codas status` (NEUTRAL, app/) — R1/R2

- CLI `codas status [path] [--json]`. New `app/status.py`.
- Build one `ScanContext` (like preflight). Affected files = `ctx.changed_paths()` (git working-
  tree diff) ∩ (the given `path`, if any).
- Run ONLY: `check_missing_structure_owner(repo, config)`, `check_deprecated_path_used(repo,
  config)`, `check_duplicate_symbol(ctx)`. FILTER each finding to those whose evidence path is in
  the affected set (for duplicate_symbol: the collision involves a symbol DEFINED in an affected
  file). Lazy ScanContext ⇒ never triggers resolution ⇒ ~100ms.
- Emit compact factual lines (text) or `--json` (list of {path, kind, message}). Empty when clean.
- §11: reuses policy functions (codas-policies) + ScanContext (codas-facts) — all allowed for
  codas-app; no adapter import, no LLM.

## 3. Hook shim (integrations/claude) — R3

- Extend the Claude installer: render + merge project-level `.claude/settings.json` hooks for
  `SubagentStop`, `PostToolUse:Agent|Task`, `PostToolUse:Edit|Write|MultiEdit`, each running a thin
  command that: runs `codas status --json`, formats findings as a factual string, prints
  `{"hookSpecificOutput": {"additionalContext": <string>}}` (or nothing when clean). Marker-guarded,
  idempotent, foreign-safe (reuse the SessionStart `_is_ours` discipline). Record in
  `.install-state.json` (extend the agent_hooks schema with these hook ids).
- The shim is a thin "run codas, wrap stdout" adapter (§17 clean — no prompt/judgment). It is the
  ONLY platform-specific piece; `codas status` itself is platform-neutral.
- The formatting (codas findings JSON → additionalContext string) can be a tiny `codas status`
  output mode OR a shell one-liner in the rendered hook; prefer a `codas status --additional-context`
  mode so the platform-specific JSON envelope is the only thing in the shim. (Decide at build.)

## 4. doctor + install-state

Extend the 1/4 diagnostics: doctor reports the per-turn hooks installed/absent (reuse
`session_hook_status` pattern — generalize it to report ALL codas-managed SessionStart/SubagentStop/
PostToolUse groups). Extend `.install-state.json` agent_hooks to record them.

## 5. Build order

(1) `app/status.py` + `codas status` CLI + tests (the neutral core, independently useful) →
(2) the additional-context output mode → (3) integrations/claude hook render+install for the 3
matchers + install-state → (4) doctor reports them → (5) gauntlet + IMPL review → commit/archive.
Ship (1)+(2) first — `codas status` is valuable on its own (manual + CI), de-risks before the hooks.

## 6. Risks / review focus

- duplicate_symbol filter: define "collision involves an affected file" precisely (a symbol DEFINED
  in a changed file that also exists elsewhere) so it does not report unrelated pre-existing dups.
- ~100ms claim: re-measure after wiring (the filter + 3 policies); confirm no policy secretly
  forces resolution. If a policy pulls `ctx.calls()`/imports, it is NOT cheap — keep it out.
- Re-report noise on repeated returns: each return re-runs over all currently-changed files; an
  unfixed finding re-injects. Acceptable as a reminder; a "since last check" delta is a later add.
- `additionalContext` size: keep compact (only changed-file findings); never dump the whole repo.
- Determinism / byte-identical: `codas status` is NOT in the inventory and must not be wired into
  `check`; confirm it cannot affect the hash.
