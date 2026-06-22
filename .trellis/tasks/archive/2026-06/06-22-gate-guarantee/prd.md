# Gate-guarantee: doctor verifies hooks + CI verifies freshness (gaps 1/4)

## Goal

Today `codas doctor` reports "install healthy" while BLIND to whether the gate (git hooks) and
injection (SessionStart hook) are actually installed, and whether the AGENTS.md block / CLAUDE.md
shim are fresh — so "healthy" is a false green (hole 1). And CI runs only `codas check`, not the
freshness `--verify`s, so a stale generated AGENTS block / wiki book passes CI (hole 2).

This task makes doctor SEE the gate + injection + freshness (consuming the install-state contract
the injection MVP wrote), and makes CI fail on stale generated docs.

## Requirements

- R1 — doctor live-probes the git hooks (`pre-commit`/`pre-push`: codas-installed / foreign /
  absent) via a NEW public `enforcement.git_hook_status(repo)`, the Claude SessionStart hook
  (installed / absent / malformed) via a NEW public `claude.session_hook_status(repo)`, and the
  AGENTS block + CLAUDE shim freshness via the existing `verify_agents_block`/`verify_claude_shim`.
- R2 — doctor reads `.codas/.install-state.json` (`read_install_state`) for the Claude `trusted`
  flag (the one thing it cannot live-probe) and surfaces `trusted=unknown` as a note (hole 4).
- R3 — the new diagnostics are WARN-level, NEVER fail: absent hooks are the NORMAL fresh-clone
  state (git hooks do not travel with a clone; install is user-controlled) and the real freshness
  gate is the CI `--verify` (R4), not doctor. doctor stays a read-only diagnostic; it SUGGESTS
  `codas hooks --install` / `codas agents --write`, never auto-installs (keeps doctor read-only).
- R4 — `enforcement.render_workflow` adds `codas agents --verify` + `codas wiki --verify` steps so
  a stale generated doc fails CI; regenerate the committed `.github/workflows/codas.yml` to match.
- R5 — §11/§17: doctor (codas-app) may call the integration status helpers (codas-app MAY depend
  on role-integrations; only codas-source/cli may not) + the app verify functions; no LLM; no
  adapter import. Deterministic. check 0; inventory byte-identical; suite green.

## Acceptance Criteria

- [ ] `codas doctor` reports git-hook + SessionStart + AGENTS/CLAUDE freshness state; on a repo
      with none installed it WARNS (does not fail); on this repo (installed) it reports them OK.
- [ ] doctor surfaces Claude `trusted=unknown` from install-state.
- [ ] CI workflow runs `codas agents --verify` + `codas wiki --verify`; committed `.github/
      workflows/codas.yml` matches `render_workflow`; test updated.
- [ ] check 0; inventory byte-identical 2x; wiki/agents --verify clean; suite green; §11/§17 clean.

## Out of scope (deferred)

- Hole 3 — per-turn injection (needs a NEW `codas status` <2s command). SEPARATE future task.
- Auto-install of hooks (doctor stays read-only; `codas hooks --install` already does it). A
  self-heal SessionStart-installs-git-hooks step is a later option, not here.
- A `--verify` for the CI workflow itself (render_workflow vs committed file drift) — pre-existing
  gap, note but do not fix here.

## Notes

- Gate-adjacent: doctor warn semantics + the committed CI artifact change -> adversarial DESIGN
  review of design.md BEFORE implementation (codex MCP unusable -> independent Claude-native
  review), THEN IMPL review. See [[never-skip-trellis-for-low-risk]].
- Consumes the doctor<->installer contract the injection MVP shipped (`read_install_state` +
  `.install-state.json` schema). See [[codas-hook-injection]].
