# Design — Codex agent integration

Companion to `prd.md`. Pins the technical shape so impl is mechanical. Reviewed by codex
before impl (per user). Worktree: `harness-codex-agent-integration` / `feat/codex-agent-integration`.

## 0. Locked decisions (from brainstorm)

- Codex first (Swift queued separately).
- Per-turn (tier 3) carrier = **Codex native hooks** (verified clone of Claude's contract),
  NOT MCP, NOT static-only.
- Static (tier 2) = AGENTS.md native, **no shim**. Git gate (tier 1) = already shared.

## 1. Current architecture (verified against `feat/codex-agent-integration` @ bebd365)

### 1a. The reusable settings-merge machinery — `integrations/claude.py`
Codex `hooks.json` and Claude `settings.json` share the SAME nested shape:
`{"hooks": {"<Event>": [ {"matcher"?, "hooks":[{"type":"command","command":…}]} ]}}`.
These helpers operate purely on `data["hooks"][event]` and are therefore **structurally
agent-neutral** — only the on-disk path differs:

- `SESSION_HOOK_MARKER` (`claude.py:30`) — trailing `# codas-managed-hook` comment marking our groups.
- `_marked` (`:140`), `_group` (`:145`), `_is_ours` (`:80`) — group construction + ownership test.
- `_merge_codas_groups` (`:152`) — replace our groups, preserve foreign, deterministic order.
- `_load_settings` (`:196`) / `_write_settings` (`:208`) — tolerant JSON read / pinned write.
- `claude_hook_status` (`:171`) / `session_hook_status` (`:91`) — live read-only probes.
- `resolve_codas_command` (`:112`), `resolve_agent_command` (`:120`), `resolve_hook_runner`
  (`:127`), `baseline_record_command` (`:217`) — command builders.
- `TurnHookSpec` (`:256`) + `turn_hook_specs` (`:266`) — the per-turn group table.

Only **two** pieces are genuinely Claude-specific in this file:
- The CLAUDE.md shim (`render_claude_shim`/`write_claude_shim`/`verify_claude_shim`, `:37–65`).
- The hardcoded `.claude/settings.json` path (every `repo / ".claude" / "settings.json"`).

### 1b. The hook ENVELOPE — `integrations/claude_hook.py`
`run_claude_hook(event)` reads stdin `cwd`, calls neutral `app.status.inject_context`, and
emits `{"hookSpecificOutput": {"hookEventName": E, "additionalContext": text}}`. This output
schema is **byte-identical** to what Codex `hooks` consume (verified vs the Codex hooks doc).
The module is already agent-neutral except its NAME and `_INJECTING_EVENTS = (Stop,
SubagentStop, PostToolUse)` (Codex uses the same event names). → Reuse, do not re-author.

### 1c. The 5 hardcoded "claude" dispatch sites
| # | site | what's hardcoded |
|---|---|---|
| 1 | `app/hooks.py:144` (+ `install_agent_injection` `:100`, `AgentInjectionResult` `:51`) | install-state key `{"agent_hooks": {"claude": …}}`; whole orchestration is claude-shaped |
| 2 | `app/doctor.py:195` `_session_state` / `:198` `_agent_hook` / `:221` `_turn_hooks` / `:265` `_claude_shim` | probe reads `agent_hooks.claude`; messages say "Claude" |
| 3 | `cli.py:202` | `claude-hook` subparser definition |
| 4 | `cli.py:281` | dispatch `if args.command == "claude-hook"` |
| 5 | `cli.py:417–449` | `hooks --install` orchestration → `install_agent_injection` |

### 1d. install-state contract — `integrations/install_state.py`
Already per-agent namespaced: `agent_hooks[<name>][<hook_key>]` via `hook_state()` +
`merge_install_state()`. The data model anticipated a second agent. `INSTALL_STATE_PATH`
gitignored + in `_IGNORE_PATHS` → never touches the byte-identical hash.

## 2. Proposed design

### D1 — Extract the generic JSON-hooks merge → `integrations/hook_settings.py` (NEW)
Move the structurally-neutral helpers (1a, minus shim + minus the hardcoded path) into a new
leaf module that takes `settings_path: Path` as a parameter:

```
hook_settings.py:
  SESSION_HOOK_MARKER, _marked, _group, _is_ours, _merge_codas_groups,
  _load_settings, _write_settings,
  group_status(settings_path, event, matcher) -> str         # was claude_hook_status
  session_group_status(settings_path, event="SessionStart")  # was session_hook_status
  install_groups(settings_path, event_specs, *, force) -> ...# the merge loop
```
`claude.py` and the new `codex.py` import these and supply only `settings_path` + per-agent
specs + (claude only) the shim. This is the DRY win the second integration unlocks.

**Risk (for review):** extraction churns the well-tested Claude path. Mitigation = pure move
(no logic change) + run the full Claude test suite green before adding Codex. **Alternative
considered:** keep helpers in `claude.py`, have `codex.py` import them from there. Rejected —
leaves the module misnamed as the "shared" home and couples codex→claude. **Recommend D1
(new neutral leaf).** ← codex: weigh extraction-risk vs the import-from-claude shortcut.

### D2 — `AgentIntegration` registry → `integrations/registry.py` (NEW) or in `app/hooks.py`
```python
@dataclass(frozen=True)
class AgentIntegration:
    name: str                               # "claude" | "codex"
    settings_path: Callable[[Path], Path]   # repo -> .claude/settings.json | .codex/hooks.json
    turn_specs: tuple[TurnHookSpec, ...]     # per-agent (see D3b)
    has_shim: bool                           # claude True, codex False
    # shim hooks (claude only): write/verify callables or None

AGENTS: dict[str, AgentIntegration] = {"claude": …, "codex": …}
```
`install_agent_injection` and the doctor probes iterate `AGENTS` (or a selected subset).
A 3rd agent later = one registry entry + (if its settings shape differs) one installer.

### D3 — `integrations/codex.py` (NEW, thin)
Mirrors `claude.py` minus shim, using D1 helpers with `settings_path = repo/".codex"/"hooks.json"`.

**D3a — settings target.** Write `<repo>/.codex/hooks.json` (repo-local, parallels
`.claude/settings.json`). Do NOT mutate `~/.codex/config.toml` (user-owned TOML; JSON file is
cleaner + isolatable). The file's top-level IS `{"hooks": {…}}` — same key the merge operates on.

**D3b — turn specs (Codex).** Drop the Claude-tool-specific matchers; keep the portable net:
- `Stop` (no matcher) — universal net (catches every worker via baseline diff).
- `SubagentStop` (no matcher) — Codex subagents.
- `PostToolUse` matcher `apply_patch|Edit|Write` — Codex's edit tool (doc: matcher reports
  `tool_name: apply_patch`; `Edit`/`Write` aliases accepted).
- DROP `Task|Agent` (Claude subagent tool) and `mcp__.*codex.*` (Claude catching codex-via-MCP)
  — both meaningless when Codex IS the host. ← codex: confirm Codex's subagent/tool names so
  the edit matcher + SubagentStop fully cover the per-turn surface.

**D3c — SessionStart.** Same two chained commands as Claude: `<codas> preflight` (digest) +
`<codas> status --record-baseline` (B1). Reuse `resolve_agent_command` + `baseline_record_command`.

**D3d — runner.** `<codas> agent-hook <Event>` (the neutralized envelope, D4).

### D4 — Neutralize the envelope
Rename `integrations/claude_hook.py` → `integrations/agent_hook.py`; `run_claude_hook` →
`run_agent_hook`; `app/hooks.py:emit_claude_turn_hook` → `emit_agent_turn_hook`. The emitted
envelope is unchanged (already neutral). **No back-compat alias** — this repo dogfoods, so the
existing Claude hooks get reinstalled (their command strings flip `claude-hook`→`agent-hook`)
as part of the task. (Existing installs on OTHER repos would re-point on their next
`hooks --install`; acceptable, pre-1.0.) ← codex: is a one-release `claude-hook` alias worth
the churn-avoidance, or is rename-only fine given dogfood reinstall?

### D5 — CLI
- Rename subcommand `claude-hook` → `agent-hook` (`cli.py:202`, dispatch `:281`).
- `hooks --install` gains `--agent {claude|codex|all}` (default **`all`** — installs every
  registry agent; matches "govern whatever agent edits this repo"). `:417–449` iterates the
  selected agents. ← codex: default `all` vs `claude` (back-compat) — `all` chosen; confirm.

### D6 — doctor
`_agent_hook` / `_turn_hooks` / `_session_state` iterate `AGENTS`, reading
`agent_hooks[<name>]` and probing each agent's `settings_path`. Codex probe also surfaces the
**repo-trust caveat** (Codex repo-local hooks may need `trust_level="trusted"` for the project
in `~/.codex/config.toml`) as an advisory `warn`, not a hard fail — parallel to Claude's
`trusted="unknown"`. `_claude_shim` stays Claude-only (gated on `has_shim`).

### D7 — install-state
`install_agent_injection` writes `agent_hooks[<name>]` per installed agent (namespace exists).
`AgentInjectionResult` generalized to hold a per-agent map instead of a single `claude` field.

## 3. Invariants to preserve (gate + boundaries)
- NOT gate-semantics: no change to `codas check`, fact extraction, or the byte-identical hash.
  `.codex/hooks.json` is a per-machine install artifact → MUST be gitignored + added to
  `_SCRATCH_IGNORES` (`app/hooks.py:64`) + `structure.index._IGNORE_PATHS` so it never
  surfaces in `codas status` or the inventory. ← codex: confirm `.codex/hooks.json` ignore
  wiring matches the `.install-state.json` precedent (BLOCKER#1).
- §11/§17: `integrations` may import `app`; the CLI may not import the envelope module
  (`agent_hook`) — it goes through `app/hooks.emit_agent_turn_hook`. Preserve.
- `duplicate_implementation` (S10): keep `run_agent_hook` a unique top-level name (not `main`).

## 4. Test plan
- `test_codex_install`: `--agent codex` writes valid `.codex/hooks.json` (4 groups), idempotent
  re-run (no dup groups), foreign group preserved.
- `test_agent_hook_envelope`: stdin `cwd` → `agent-hook <Event>` emits identical envelope on a
  dirty repo, nothing (exit 0) on clean. Parametrize claude vs codex runner string.
- `test_codex_no_shim`: Codex install creates NO CLAUDE.md; AGENTS.md block is the static carrier.
- `test_doctor_codex`: doctor reports codex installed/stale/absent from `.codex/hooks.json` +
  `agent_hooks.codex`; emits the trust advisory.
- `test_registry`: `AGENTS` has claude+codex; `--agent all` installs both; doctor iterates.
- Regression: full existing Claude suite green after D1 extraction + D4 rename.
- `codas check .` = 0; inventory byte-identical (prove `.codex/hooks.json` excluded).

## 5. Dogfood + sequencing
1. D1 extract + run Claude suite green (de-risk first).
2. D4 rename envelope + reinstall Claude hooks on this repo (verify still inject).
3. D2 registry + D3 codex.py + D5 CLI + D6 doctor + D7 state.
4. `codas hooks --install --agent all` on this repo → `.codex/hooks.json` written (gitignored).
5. Verify a Codex session in this repo picks up AGENTS.md + the per-turn injection.

## 6. Open questions for codex review
1. D1 extraction risk vs import-from-claude shortcut — worth the churn?
2. D3b — do Codex's subagent + edit tool names fully covered by `SubagentStop` +
   `apply_patch|Edit|Write`? Any missed per-turn surface (e.g. `UserPromptSubmit` as an
   earlier-firing carrier)?
3. D4 — rename-only vs a one-release `claude-hook` alias?
4. D5 — `--agent all` default acceptable, or keep `claude`-only for back-compat?
5. §3 — is `.codex/hooks.json` the right artifact vs inline `[hooks]` in `.codex/config.toml`
   for a repo a user may want to COMMIT hooks into? (We assume per-machine/gitignored.)
6. Any reason the SessionStart `additionalContext` (Codex) needs `hookEventName:"SessionStart"`
   while our envelope omits SessionStart from `_INJECTING_EVENTS` (digest rides the chained
   `codas preflight` command, not the envelope) — does Codex's SessionStart inject preflight's
   stdout the same way Claude does?
