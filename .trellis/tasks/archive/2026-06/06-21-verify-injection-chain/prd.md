# Verify agent-injection chain end-to-end (dogfood)

## Goal

Prove the shipped injection MVP works on THIS repo, not just in unit tests. A verification /
dogfood task (no product code changes) — it also becomes the FIRST real `related_files` task,
so the preflight digest lights up with non-empty sections.

## Chain to prove

1. **Governance block live** — `codas agents --verify` clean; AGENTS.md + CLAUDE.md committed.
2. **Preflight digest populates** — this task declares `relatedFiles`; `codas preflight --task
   verify-injection-chain` returns non-empty affected_units + reuse_candidates + advisory_why.
3. **`codas hooks --install`** — installs git pre-commit/pre-push + the Claude SessionStart hook,
   writes `.codas/.install-state.json` (git_hooks + agent_hooks + agents_block/claude_shim).
4. **SessionStart injection runs** — the installed hook command emits the preflight pack to stdout.
5. **Idempotent re-install** — second `hooks --install` is a no-op (no settings.json byte churn).
6. **BLOCKER#1 live** — `.install-state.json` absent from `codas inventory`; inventory byte-identical.
7. **Gate still holds** — `codas check` 0 after install.

## Acceptance Criteria

- [ ] digest non-empty for this task (affected_units include codas-app + role-integrations).
- [ ] install-state contract written with all keys; SessionStart hook present + marker-guarded.
- [ ] re-install idempotent; inventory byte-identical; install-state out of the hash; check 0.

## Notes

- No product behavior change. The only committed artifacts are this task + (decision) the
  `.claude/settings.json` if we keep the live install.
- Gate-semantics unaffected (no policy/scanner change) -> no codex DESIGN review needed.
