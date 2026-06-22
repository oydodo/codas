# Codex agent integration — native-hook injection (gate + AGENTS.md + per-turn) via reused envelope + agent registry

## Goal

Make Codas govern an OpenAI **Codex CLI** agent with the same three-tier coverage it
gives Claude Code today: (1) the git gate, (2) the static governance norms, and (3) the
per-turn advisory injection. Codex is the second integration; introduce the agent seam
the codebase has been deferring (today "claude" is hardcoded at 5 sites with no registry).

## Background / research (closed 2026-06-22)

Codex CLI ships a **near-clone of Claude Code's hook contract** (verified against
developers.openai.com/codex/hooks + config-reference):

- Hooks declared in `<repo>/.codex/hooks.json` **or** inline `[hooks]` in
  `.codex/config.toml`; discovered per config layer (`~/.codex/` global, `<repo>/.codex/`
  repo-local).
- Same event names: `SessionStart`, `Stop`, `SubagentStop`, `PostToolUse`,
  `UserPromptSubmit`, `PreToolUse`, `Pre/PostCompact`.
- Same stdin-JSON context (`cwd`, `session_id`, `hook_event_name`, `tool_name`, …).
- **Same injection envelope**: `{"hookSpecificOutput": {"hookEventName": E,
  "additionalContext": text}}` — byte-identical to what `integrations/claude_hook.py`
  already emits.
- Matcher = regex on `tool_name`; file-edit token is `apply_patch|Edit|Write`
  (Codex equivalent of Claude's `Edit|Write|MultiEdit`).
- `command` hooks supported (prompt/agent handlers parsed-but-skipped). Exit-2+stderr =
  block; stdout JSON = context.

**Consequences for scope:**
- Tier 1 (git gate) is already agent-neutral/shared — no Codex work.
- Tier 2 (static norms) is **free**: Codex reads `AGENTS.md` natively; the verified
  `AGENTS.md` block already exists. **No CLAUDE.md-style shim** (Codex has no shim
  concept; `model_instructions_file`/AGENTS.md is native).
- Tier 3 (per-turn) is fully achievable via Codex **native hooks** — NOT MCP, NOT
  static-only. The hook envelope (`claude_hook.py`) is already agent-neutral in its
  output schema → reuse, do not re-author.
- `install_state` is already per-agent namespaced (`agent_hooks[{name}]`) — the data
  model anticipated a second agent.

Out of scope: Swift / multi-language extraction (separate queued task); MCP carrier
(unnecessary now that native hooks cover tier 3).

## Requirements

### R1 — Reuse the hook envelope (neutralize naming)
- `integrations/claude_hook.py` emits the shared `additionalContext` envelope. Rename to
  a neutral `integrations/agent_hook.py` / `run_agent_hook(event)`; both Claude and Codex
  hook configs invoke it.
- CLI: expose neutral `codas agent-hook <Event>` (keep `claude-hook` as a thin alias OR
  reinstall — this repo dogfoods, so a reinstall is acceptable; pick one and state it in
  design). The envelope content (`app.status.inject_context`) stays untouched/neutral.

### R2 — Codex installer (`integrations/codex.py`)
- Write the SessionStart + per-turn hook groups to `<repo>/.codex/hooks.json`
  (repo-local, parallel to `.claude/settings.json`). Choose `hooks.json` over inline
  `[hooks]` in config.toml (cleaner, JSON, mirrors settings.json; do not mutate the
  user's `config.toml`).
- SessionStart hook chains the same two commands the Claude hook does (`codas preflight`
  digest + `codas status --record-baseline`).
- Per-turn hooks: `Stop`, `SubagentStop`, `PostToolUse` (matcher `apply_patch|Edit|Write`
  for edits; the existing `mcp__.*codex.*` matcher is Claude-side, N/A here) → each runs
  `codas agent-hook <Event>`.
- Marker convention mirrors the Claude installer so groups are idempotently
  detected/updated/removed.

### R3 — Agent registry (replace hardcoded "claude")
- Introduce an `AgentIntegration` descriptor (name, settings target, render-hooks,
  verify, status-probe) with `{"claude": …, "codex": …}` registry.
- Replace the 5 hardcoded "claude" dispatch sites:
  `app/hooks.py:144` (install-state key), `app/doctor.py:195` (probe lookup),
  `cli.py` subcommand def + dispatch branch + `hooks --install` orchestration.
- `codas hooks --install --agent {claude|codex|all}` (default `all` or current behavior;
  state the default in design). Doctor iterates the registry.

### R4 — install-state + doctor
- Write Codex hook state under `agent_hooks["codex"]` (namespace already exists).
- Doctor probes `<repo>/.codex/hooks.json` health (group presence by event/matcher,
  command freshness) parallel to the Claude probes.
- Doctor surfaces the Codex repo-trust caveat (repo-local hooks may require Codex
  `trust_level = "trusted"` for the project) as an advisory, not a hard failure.

### R5 — AGENTS.md static tier (verify, do not rebuild)
- Confirm the existing verified `AGENTS.md` block satisfies Codex's static tier with no
  new shim. Add a test asserting Codex needs no shim file.

## Acceptance Criteria

- [ ] `codas hooks --install --agent codex` writes a valid `<repo>/.codex/hooks.json`
      with SessionStart + Stop + SubagentStop + PostToolUse groups; re-running is
      idempotent (no duplicate groups).
- [ ] A Codex hook invocation (stdin `cwd` JSON → `codas agent-hook <Event>`) emits the
      `hookSpecificOutput.additionalContext` envelope identical to the Claude path on a
      dirty repo, and emits nothing (exit 0) on a clean turn.
- [ ] The hook envelope module is agent-neutral (renamed); the Claude path still works
      (alias or reinstall, per design).
- [ ] No CLAUDE.md-style shim is created for Codex; the existing AGENTS.md block is the
      static carrier (test asserts this).
- [ ] `codas doctor` reports Codex integration health (installed/stale/missing) by
      reading `.codex/hooks.json` + `agent_hooks["codex"]`, and notes the repo-trust
      caveat.
- [ ] The 5 hardcoded "claude" sites are replaced by the registry; adding a 3rd agent
      would touch only a registry entry + an installer module (state this seam in design).
- [ ] `codas check .` = 0; byte-identical inventory preserved (no gate/fact/hash change);
      full test suite green; new tests cover the Codex installer + doctor probe + envelope
      reuse.

## Constraints

- NOT gate-semantics: must not touch `codas check`, fact extraction, or the byte-identical
  hash. Inventory stays byte-identical. (codex DESIGN review optional — the registry seam
  is the only real design call; recommended but not mandated.)
- `integrations` may import `app` (permitted direction); the CLI may not import the hook
  entrypoint module (existing §11/§17 boundary — preserve it).
- Dogfood it: install the Codex integration on this repo as part of the task (parallel to
  the existing Claude hooks), like prior injection tasks did.

## Notes

- Sources: https://developers.openai.com/codex/hooks ,
  https://developers.openai.com/codex/config-reference
- Follow-up (separate task, queued): Swift / multi-language extraction via tree-sitter,
  thin slice (symbols+imports), target repo `/Users/oydodo/Documents/repo/swift/ciri`.
- A short `design.md` is worth adding before impl to pin: agent-hook naming
  (alias vs rename-only) + `--agent` default + the `AgentIntegration` descriptor shape.
