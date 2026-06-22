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

## 7. FOLDED design-review changes (workflow wf_cce9c4b1-2ad, 3-lens — APPROVE-WITH-CHANGES)

codex MCP unusable → Claude-native 3-lens adversarial review. The ~100ms premise was VERIFIED
SOUND (lazy ScanContext is real; relabel the NUMBER). Build to these.

**B1 (BLOCKER) — committed-worker empty-diff blinds the check exactly when it matters.** The main
worker class (codex/tmux, many Claude subagents) COMMITS before returning, so at the return
boundary the working tree is CLEAN → `changed_paths()` = () → status silent → gap-3 stays open for
exactly the workers we care about. FIX: do NOT derive scope from working-tree-vs-HEAD alone.
Record a session/delegation BASELINE commit sha (at SessionStart, and/or when a delegation is
dispatched) and add `codas status --since <ref>` = `git diff baseline..HEAD` ∪ working-tree. Store
the baseline in a gitignored scratch (see S2). At minimum, surface the empty-diff case explicitly
rather than silently claiming universality.

**B2 (BLOCKER) — duplicate_symbol is src/-hardcoded + the filter IS new logic.** `duplicate_symbol.py`
hardcodes `SCOPE_PREFIX='src/'` and takes no affected-set param. (a) The "filter to changed files"
is a status-specific POST-filter over `Finding.evidence` → that IS new logic that can diverge from
the gate — DROP the "no new logic" framing; spell the filter out as a precise TESTED predicate in
`app/status.py` (a duplicate finding counts iff a symbol DEFINED in an affected file also exists
elsewhere). (b) On a non-`src/` layout (lib-/app-layout) status silently reports ZERO duplicate
findings while advertising it as one of three pillars — either DOCUMENT "duplicate-symbol status is
src-only (matches the policy's scope)" OR make `duplicate_symbol` honor `wiki.product_roots` (the
cross-repo work never reached it). MVP: document the limitation + a test pinning it.

**S1 — strip imperative recommendations.** All three policies carry imperative `recommendation`
fields ("Add a Structure Unit…", "Move it under…", "Consolidate…"). Claude's prompt-injection
defense flags out-of-band imperatives. Emit ONLY `{path, kind, message}` (factual); drop
`recommendation` from text AND --json; TEST that no imperative leaks into `--additional-context`.

**S2 — ship the dedup, don't defer it.** `changed_paths()`/baseline-diff grows monotonically in a
session → every return re-injects every standing finding; and the receiver is the MAIN agent (didn't
author the code) → an unactionable finding (owner needs a human structure.yml decision) drives a
re-delegate/re-inject LOOP. FIX: fingerprint injected findings (hash of path+kind+message) in a
gitignored `.codas/.status-seen.json` (add to BOTH `.gitignore` AND `index.py::_IGNORE_PATHS`, like
`.install-state.json`); inject only unseen; add an "unactionable → suppress after N / needs-human"
carve-out. This scratch also holds the S/B1 baseline sha.

**S3 — hard-cap the additionalContext payload (TESTED).** missing_owner emits one finding per
unowned artifact, re-injected every return → erodes the very context window this protects. Top-N
(e.g. 10) + deterministic order + a "+K more, run `codas status`" tail + a byte cap, as a tested
invariant, not prose.

**S4 — the REAL universal net is the `Stop` hook (mcp-codex is NOT caught at return otherwise).**
`PostToolUse:Agent|Task` + `SubagentStop` fire ONLY for the native Task/Agent tool — **mcp-codex
workers spawn via `mcp__*` tools, so NO return-boundary hook matches them, and that is the user's
PREFERRED backend (global CLAUDE.md).** FIX: make the `Stop` hook (fires when the MAIN agent yields
its turn — catches EVERYTHING git-visible regardless of who edited) the real universal net; DEMOTE
SubagentStop/PostToolUse:Agent to earlier-firing optimizations; also add a `PostToolUse` matcher for
the MCP codex tool name(s) (`mcp__*codex*`). State explicitly that mcp-codex changes surface at the
next `Stop`/edit. (Stop + baseline-diff from B1 = the actually-universal combination.)

**S5 — budget the COLD cost; never block/crash the turn.** The ~150ms is IN-PROCESS after imports;
the hook spawns a fresh `python3 -m codas status` per fire (cold interpreter + codas/adapters/yaml
import ≈ 300–600ms wall), synchronously on every fire. FIX: (a) budget end-to-end COLD with ~200ms+
headroom; (b) hook `timeout` so a stalled git/status never blocks the turn; (c) drop/debounce
`PostToolUse:Edit` to avoid the per-edit tax (Edit can also fire mid-edit on a syntactically broken
file); (d) `parse_python_modules` must skip SyntaxError files (test it) and the whole status path
must be wrapped so ANY exception → exit 0 + empty additionalContext ("status NEVER raises" invariant).

**S6 — generalize the install/state model to (event, matcher) groups.** `install_claude_session_hook`
/ `_is_ours` / `session_hook_status` are hardwired to one `hooks.SessionStart` group; the new hooks
live under `Stop`, `SubagentStop`, and matcher-keyed `PostToolUse`. Specify the schema before build:
`agent_hooks.claude.{session_start, stop, subagent_stop, post_tool_use_agent, post_tool_use_edit}`
each a `hook_state`; generalize the installer + a `claude_hook_status(repo, event, matcher)` doctor
calls per group; reuse the `# codas-managed-hook` marker per group; PRESERVE foreign matchers in the
same event; keep the doctor hyphen→underscore key convention collision-free. Tests: foreign
PostToolUse:Edit preserved; re-install idempotent across all events; partial install.

**S7 — restate the perf budget honestly.** "~100ms" is symbol-only-in-isolation; the FULL status
path measured ~145–155ms (dup_symbol ~77ms parse + missing_owner ~23 + deprecated_path ~21 +
changed_paths ~16 + ctx ~10) and scales with the parse of ALL `.py` under the workspace root.
Restate everywhere as "~150ms on this ~150-file repo, scaling with full-tree parse"; assert
acceptance against ~200ms+ headroom. Re-measure after wiring.

**S8 — fix the "one ScanContext drives all three" framing (§2/§6).** `missing_owner.py` +
`deprecated_path.py` take `(repo, config)` NOT `(ctx)`; each re-runs its OWN `discover_files`
(missing_owner also rebuilds `build_artifact_index`) → a status run does THREE file scans and
`ctx.files` is computed-then-ignored by 2 of 3. Only `duplicate_symbol(ctx)` is resolution-adjacent;
ITS laziness is what holds the budget. Correct §2/§6 to the real signatures (accept the cheap
3-scan duplication for MVP, or note a future `ctx.files` dedupe).

**S9 — state the git precondition + degraded behavior.** No-commits / non-git / mid-rebase →
`extract_changed_paths()` returns () → hook silently inert. `codas status` must DISTINGUISH "clean"
from "no git baseline"; doctor surfaces "inert: no git" when the hook is installed but can't function.

**S10 — dogfood the gate on the new source.** `app/status.py` + CLI wiring are themselves governed.
Build plan: after wiring, `codas check .` 0 + inventory byte-identical 2x; confirm new public symbol
names (`run_status`/`status`/…) don't collide under duplicate_symbol's src/ scope.

**NITS:** N1 changed-file filtering is OUTPUT-scoping/noise control, NOT a speedup (the ~150ms floor
is the full-tree parse; doesn't shrink with a smaller diff) — note it so "why still 150ms for one
file" isn't a surprise. N2 duplicate_symbol's src/ + public-only (non-underscore) scope narrows
coverage — don't claim universal "symbol already exists." N3 state the bound (findings ≤ dirty×3,
re-injected until fixed/committed) — superseded by S2 dedup. N4 factual-phrasing rests on a
model-behavior assumption that can drift; keep phrasing tunable + empirically verify injected
findings actually change main-agent behavior.

**REVISED trigger (folding B1+S4):** the load-bearing pair is **`Stop` hook + baseline-diff** (catches
every worker incl. mcp-codex/committed, because it checks git since the session baseline whenever the
main agent yields). SubagentStop / PostToolUse:Agent / PostToolUse:Edit are earlier-firing
optimizations on top. All inject the MAIN agent, factually, deduped, capped, never-raising.

## 8. IMPLEMENTED + IMPL-review (workflow wf_1b15bf1a-7b8, 4-lens — codex unusable → Claude-native)

SHIPPED: `app/status.py` (neutral core, ~150ms, never-raises) · `codas status [--since|--since-baseline|
--json|--additional-context|--record-baseline]` · `integrations/claude_hook.py` envelope entrypoint +
`codas claude-hook <Event>` CLI subcommand · generalized (event,matcher) installer
(`install_claude_turn_hooks`: Stop/SubagentStop/PostToolUse×3 incl. `mcp__.*codex.*`) + SessionStart
2-command group (preflight + `status --record-baseline`) · doctor `_turn_hooks` (per-group probe + S9
inert) · dedup scratch `.codas/.status-seen.json` (gitignored + `_IGNORE_PATHS`). The verified Claude
contract (`{"hookSpecificOutput":{"hookEventName","additionalContext"}}` + exit 0; matcher = JS-regex;
Stop has no built-in loop guard → our dedup IS the guard) drove the shim. B1 proven end-to-end: a worker
that COMMITS before returning is invisible to the working-tree diff but caught by the baseline diff.

4-lens adversarial review → 1 blocker + 6 should + 5 nits. ALL fixed except N5 (note-only):
- **B1 (blocker, FIXED):** installed runner was bare `python3 -m codas.integrations.claude_hook` →
  ModuleNotFoundError at IMPORT time (before the never-raises guard) when codas is pipx/venv-installed
  with a different `python3`, exiting 1 every turn. Fixed by routing through a `codas claude-hook` CLI
  subcommand so the runner resolves the SAME base codas invocation as SessionStart (symmetric).
- **S1 (FIXED):** dedup marked ALL fresh findings seen but only the rendered (capped) subset injects →
  capped-out findings silently dropped. Now persists exactly the rows `_shown_rows` returns.
- **S2/N1 (FIXED):** a stale/orphaned `--since` baseline silently degraded to a clean-looking run. Now
  `ref_resolves` → `git="stale-baseline"` surfaced in render_text (self-heals at next SessionStart).
- **S3 (FIXED):** install now appends the scratch files to the consumer `.gitignore` (idempotent).
- **S4 (FIXED):** byte-identical re-install now reports `installed` (was always `refreshed`).
- **S5/S6/N2/N3/N4 (tests/guards added):** both-sides-changed dup fan-out · doctor malformed+partial
  branches · envelope over all 3 events + non-injecting event · imperative-blacklist over all 3 kinds ·
  oversized-single-finding → empty (no header-only noise).
- **N5 (NOTE only, pre-existing, out of scope):** `test_book` runs `write_book(Path.cwd())` against the
  REAL repo — benign while the committed book stays fresh (CI `wiki --verify` enforces it), but it
  re-renders the working-tree book during a suite run. This task surfaced + regenerated the book for the
  new symbols. A future cleanup: point `test_book` at a temp copy instead of mutating cwd.

GAUNTLET: 563 tests green · `check` 0 · inventory byte-identical 2× · agents/wiki `--verify` clean ·
book regenerated for the new public symbols (`ref_resolves`, `emit_claude_turn_hook`, …).
