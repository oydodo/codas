# Agent norm-injection MVP (gaps 2/3)

## Goal

Make Codas's verified governance **reach the main coding agent BEFORE it works**, not only
gate it at commit. Today injection is weak: passive (`AGENTS.md`, which Claude Code does not
even read natively) + opt-in pull (`codas preflight`). This task builds the **injection /
effectiveness** half. The **enforcement / guarantee** half (gaps 1/4 — `doctor` verifies the
hooks, auto-install) is a SEPARATE task; the two are sequential, but their install-state
**marker contract is co-designed here** (see design.md §6).

## The two-tier correctness framing (codex DESIGN review — corrects the original "injection = pure efficiency")

Injection is NOT merely efficiency. The commit gate (`run_check`) formalizes only a subset:

- **GATED (hard invariants — guaranteed by check + verify + inventory, not check alone; codex
  A1):** missing Structure owner, structure drift, deprecated-path use, `duplicate_implementation`
  (top-level name collision), dependency direction, byte-identical determinism; plus
  verify-enforced freshness (`generated_wiki_drift` via `codas wiki --verify`).
- **UNGATEABLE today (the gate is SILENT):** "wrong unit but still owned," semantic reuse
  misses, wrong abstraction / hook-point. `duplicate_concept` is `planned` (inactive);
  `duplicate_symbol` is warning-only.

So injecting the **ownership/placement map + reuse candidates** is **load-bearing for
correctness** on the decisions the gate cannot yet formalize — not just rework-avoidance.
Two tiers: the gate guarantees the formalizable invariants; injection is the only defense for
design-quality correctness (placement / reuse / abstraction).

## Scope — MVP (Claude Code only)

1. **AGENTS.md Codas governance block** — a delimited, Codas-managed section (markers,
   preserve everything outside) that is a DETERMINISTIC projection of `.codas/policies.yml` +
   `.codas/structure.yml`, registered with `--verify` (so it cannot silently drift). Content:
   the **policy catalog** (each policy + one-line "what it catches" + which failure classes are
   ungateable), a **compact ownership/placement map** (unit -> path -> owner -> canonical_placement),
   and the **lookup protocol** (when to run `codas query`/`impact`/`schema`/`preflight`).
2. **`preflight --task` upgrade (point -> DIGEST), session-start only** — add **reuse
   candidates** (existing symbols matching what the task adds) + **affected units** + their
   **why-prose** read from the `.codas/wiki/code/<unit>.md` SOURCE, **explicitly labelled
   advisory** (section 17). Runs once at session start (latency tolerable); NOT per turn.
3. **`CLAUDE.md` shim** — Claude Code reads `CLAUDE.md`, not `AGENTS.md`; write/patch a
   `CLAUDE.md` that imports `@AGENTS.md` (or a symlink), verified for freshness.
4. **Claude Code `SessionStart` hook** — installer (in `integrations/`) that merges a
   `SessionStart` hook into `.claude/settings.json` running `<abs>/codas preflight` and
   injecting stdout. Marker-guarded, idempotent, never clobbers a foreign hook, absolute
   `codas` path. Emits install-state markers for `doctor` (the 1/4 contract).

## Out of scope — DEFERRED (codex MVP cut)

- **Per-turn live hook** (`UserPromptSubmit`) — needs a NEW small `codas status` / `preflight
  --check` command (<2s, state-change delta only); the full `--task` digest per turn blows the
  10k-char / 30s caps. Deferred until that command exists.
- **Codex `config.toml` hook** — TOML installer; Codex hook support is research-claimed but
  UNCONFIRMED in-repo -> re-verify at that task's build time. Deferred.
- **Cursor** — `sessionStart`-only injection (degrades; its per-prompt hook can't inject).
  Deferred.
- **Layer 3 PreToolUse deny hook + JIT pointer** — over-engineered for V1, risks confusing
  advisory injection with a hard gate. Deferred.
- **MCP agent-query interface** — the P7-noted optional transport. Deferred.

## Requirements

- R1 — A `codas`-managed AGENTS.md block, a deterministic projection of policies.yml +
  structure.yml (sorted, no timestamp, byte-identical), written between markers preserving the
  Trellis block + all hand content, registered with the existing `--verify` machinery.
- R2 — `preflight --task` returns reuse candidates + affected units + advisory-labelled
  why-prose, deterministically; computed once (session-start), not per turn.
- R3 — A `CLAUDE.md` shim importing `@AGENTS.md`, freshness-verified.
- R4 — A Claude Code `SessionStart` hook installer: JSON merge into `.claude/settings.json`,
  marker-guarded, idempotent, foreign-hook-safe, absolute `codas` path; emits install-state
  markers.
- R5 — `doctor`<->installer marker contract DEFINED here (consumed by the 1/4 task).
- R6 — Determinism preserved: AGENTS block + CLAUDE shim are deterministic renders; `codas
  check` 0, inventory byte-identical, verify clean. Section 17 (no LLM in core; hook is a thin
  "run codas, emit stdout" shim, no embedded prompt/judgment), section 11 (core/app neutral;
  `integrations/` is the only platform-specific layer; no policy/hash/gate references platform
  config).
- R7 — policies.yml commentary documents which placement/reuse failure classes are ungateable
  (so injection scope is not undersold as "just efficiency").

## Acceptance Criteria

- [ ] AGENTS.md Codas block renders deterministically from policies.yml + structure.yml; editing
      either regenerates it; verify flags a hand-edit / drift; Trellis block + hand content
      preserved.
- [ ] `preflight --task` digest includes reuse candidates + affected units + advisory why-prose;
      deterministic 2x; why-prose explicitly marked advisory.
- [ ] `CLAUDE.md` shim imports `@AGENTS.md`; freshness-verified.
- [ ] `codas hooks --install` (or `codas init`) merges the Claude `SessionStart` hook into
      `.claude/settings.json` without clobbering; re-run is idempotent; uses an absolute `codas`
      path; sets install-state markers.
- [ ] `codas check` == 0; inventory byte-identical 2x; verify clean; full suite green; section
      11/17 clean.
- [ ] Deferred items (per-turn hook, Codex, Cursor, Layer 3, MCP) recorded, not built.

## Notes

- Gate-adjacent (a NEW verified artifact = the AGENTS block + verify registration) -> codex
  DESIGN review of the WRITTEN design.md BEFORE implementation, THEN codex IMPL review. The
  adversarial DESIGN DISCUSSION is already done (verdict SOUND-WITH-CHANGES, folded into this
  prd + design); the written design still gets one codex DESIGN pass.
- Roadmap: this is the P8/P9 injection strand. After it: the `codas status` per-turn command ->
  per-turn hook; then Codex/Cursor adapters; then Layer 3.
</content>
