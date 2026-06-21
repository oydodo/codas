# Design — Agent norm-injection MVP (gaps 2/3)

Concrete change map for the MVP (Claude Code only). Folds the codex DESIGN-DISCUSSION
(SOUND-WITH-CHANGES) AND the written-design codex DESIGN review (APPROVE-WITH-CHANGES). Build
to the must-holds below; then codex IMPL review.

## FOLDED codex DESIGN review (APPROVE-WITH-CHANGES — build to THESE)

The 6 must-hold constraints (woven into the sections below; restated here as the build gate):

1. **(Q4 BLOCKER, do FIRST)** Add `.codas/.install-state.json` to BOTH `.gitignore` AND the
   non-git scanner fallback `index.py::_IGNORE_PATHS` (line 19) BEFORE any install code runs —
   else the machine-local marker leaks into the byte-identical inventory. (§6)
2. **(Q1)** `app/agents_block.py` pure + deterministic; may import the config/structure LOADERS,
   must NOT import `codas.adapters.*` or `integrations/`. (§1, §7)
3. **(Q3)** Verify via a NEW `codas agents --verify` (or `codas install --verify`) — do NOT
   extend `codas wiki --verify`. (§1, §3)
4. **(Q5)** The AGENTS block renderer must NOT wrap extension-bearing paths in backtick code
   spans or markdown links (the ownership table surfaces unit paths like `.codas/policies.yml` /
   `src/codas/app/preflight.py` — a slash+known-ext span becomes a real `doc_claim` and churns
   the hash). SAFE: policy ids, unit ids, `` `codas query` `` command spans, extension-LESS dir
   paths (`src/codas/app`), plain table cells. (§1)
5. **(A2)** Expand the `.install-state.json` schema before writing it: `schema_version`, per-hook
   `status` (installed/stale/foreign/skipped/absent), `expected_command`/`installed_command`,
   `marker_id`, Claude `trusted`. (§6)
6. **(A4)** Because the schema carries `git_hooks`, RETROFIT the existing
   `enforcement.py::install_hooks` to write its `git_hooks` key — the schema must not describe
   state no installer emits. (§6)

**(A1 framing correction, into prd.md):** the two-tier framing is accurate but NOT "solely
check-gated" — `generated_wiki_drift` freshness is enforced by `codas wiki --verify`, not the
check gate. State the guarantee as **check + verify + inventory**, not check alone. `app/`
placement, the no-per-turn digest scope, the hook shim's §17 cleanliness, and the advisory
why-prose out-of-hash were all CONFIRMED clean.

## 0. Architecture (layers, and where each lives)

```
NEUTRAL CORE (app/, platform-agnostic, deterministic, --verify'd)
  - AGENTS.md Codas block renderer        (projection of policies.yml + structure.yml)
  - preflight --task DIGEST upgrade        (reuse candidates + affected units + advisory why-prose)
PLATFORM SHIM (integrations/, the ONLY platform-specific layer)
  - CLAUDE.md shim writer                  (@AGENTS.md import)
  - Claude Code SessionStart hook installer (.claude/settings.json JSON-merge)
  - install-state markers                  (the doctor<->installer contract, consumed by 1/4)
```

NB codex suggested the AGENTS renderer live in `integrations/enforcement.py`. We place the
NEUTRAL renderer in `app/` instead — it is platform-agnostic (every agent reads AGENTS.md), so
putting it in `integrations/` would muddy codex's own agnosticism line (B): keep `integrations/`
a THIN platform shim, keep neutral deterministic renders in `app/` (mirrors `app/book.py` /
`app/wiki.py`). Only the CLAUDE.md shim + settings.json hook are platform-specific -> `integrations/`.

## 1. AGENTS.md Codas governance block (R1) — the freshness-critical piece

The single biggest real build (codex C1: no AGENTS managed-block generator/verifier exists yet,
so today `--verify` CANNOT catch policy/structure-catalog drift).

- **Renderer** `app/agents_block.py`: `render_codas_block(policies_raw, structure_map) -> str`,
  a PURE deterministic projection (sorted, no timestamp). Sections:
  - **Policy catalog** — from `.codas/policies.yml`: each policy id + severity + a one-line
    "what it catches" (a static description map keyed by policy id, NOT free prose) + a
    GATED/UNGATEABLE tag (so the agent learns which failure classes the gate is silent on).
  - **Ownership/placement map** — from `.codas/structure.yml`: a compact table unit ->
    path -> owner -> canonical_placement (the placement rule the gate cannot enforce).
  - **Lookup protocol** — a static block: which `codas query`/`impact`/`schema`/`preflight`
    command answers which question (the "where to look up" pointer; the agent's table is the
    P7 query surface, NOT the rendered wiki/ book).
- **Write/verify** `app/agents_block.py::write_agents_block(repo)` / `verify_agents_block(repo)`:
  splice ONLY between `<!-- CODAS:START -->` / `<!-- CODAS:END -->` markers; preserve the
  Trellis block + every byte outside the Codas markers (mirror `enforcement.py`'s marker
  discipline + `book.py`'s write_bytes/read_bytes LF-pin). **codex Q3: expose verification via a
  NEW `codas agents --verify`, NOT an extension of `codas wiki --verify`** (wiki verify fans in
  only Atlas sections + book pages; AGENTS/CLAUDE freshness is the agent-instruction surface, a
  distinct concern). `codas agents --verify` byte-compares the AGENTS block + the CLAUDE shim to
  a fresh render so a hand-edit or a policies.yml/structure.yml drift is caught.
- **Determinism/hash:** AGENTS.md is a COMMITTED supporting source (scanned). The block is a
  committed deterministic render -> it IS in the inventory (like `.codas/wiki/generated/**`),
  and `--verify` byte-compares it to a fresh render. Editing policies.yml/structure.yml
  regenerates it -> inventory legitimately reflects it. NOT out-of-hash; it is a verified
  generated section. (Confirm in design review: does AGENTS.md being scanned + a regenerated
  block introduce any doc_claims churn? The block uses prose + policy ids, no new real-path
  code spans, so no new doc_claims — verify.)

## 2. preflight --task DIGEST upgrade (R2) — session-start only

`app/preflight.py::build_context_pack(repo, task_id)` today POINTS. Add a DIGEST, computed
ONCE at session start (latency tolerable; NOT per turn — codex D3):

- **reuse candidates** — existing top-level symbols whose name/shape matches what the task is
  likely to add. MVP heuristic: surface the symbols in the task's declared package/affected
  units from the inventory `symbols` block (deterministic), so the agent sees "these already
  exist here" before writing a duplicate the gate won't catch (duplicate_concept is `planned`).
- **affected units** — the units owning the task's touched paths. codex D1: `build_context_pack`
  has no touched-paths param and `impact` does a fresh scan per target (too slow per-turn). For
  the SESSION-START digest this is fine (run once); derive affected units from the task's
  declared scope/package via the inventory `units` (no per-turn `impact`).
- **why-prose** — read `.codas/wiki/code/<unit>.md` SOURCE for each affected unit, strip the
  `atlas:claims` fence (reuse `book.py::_strip_claims_block`), include under an **explicitly
  labelled `advisory_why` key** (codex D2/E: §17 — the agent must not treat prose as normative;
  no policy/hash/gate reads it). Out-of-hash source, so a between-sessions prose edit silently
  changes the pack — acceptable (advisory), documented.
- Keep it DETERMINISTIC (sorted, content-hashed, no timestamp). The per-turn payload is a
  SEPARATE future command (`codas status`), NOT this.

## 3. CLAUDE.md shim (R3) — integrations/

Claude Code reads `CLAUDE.md`, not `AGENTS.md`. `integrations/claude.py::write_claude_shim(repo)`
writes/patches a root `CLAUDE.md` containing a single `@AGENTS.md` import line inside a
`<!-- CODAS:START -->`/`END` marker (preserve any existing CLAUDE.md content outside). Freshness:
`verify_claude_shim` confirms the import line is present + points at `AGENTS.md`; folded into the
same `codas agents --verify` surface as §1. NB the shim WRITER is platform-specific
(`integrations/`), but its VERIFY is a neutral byte-compare callable from `app/`.

## 4. Claude Code SessionStart hook installer (R4) — integrations/

`integrations/claude.py::install_claude_hooks(repo)`:
- Read-modify-write `.claude/settings.json` (JSON-aware; NEVER blind text-append — codex P4).
  Merge a `SessionStart` matcher-group whose command is `<abs>/codas preflight` (absolute path
  — codex P6: `codas` may not resolve on PATH in a non-interactive `sh -c`; resolve via
  `shutil.which` or the install prefix).
- Marker the hook (`# codas-managed-hook` analogue in a JSON comment-field / a recognizable
  command wrapper) so re-install is idempotent and a FOREIGN hook is never trampled (mirror
  `enforcement.py::install_hooks` discipline).
- Trust: the install can't be fully silent (Claude workspace-trust dialog). The installer
  PRINTS the "approve the hook in Claude" step; `doctor` later reports installed-but-untrusted.
- stdout caps: `preflight` output must stay well under the per-event limits; SessionStart is
  not the 10k/30s-capped per-turn path, but keep the pack compact.

## 5. policies.yml ungateable commentary (R7)

Add YAML comments to `.codas/policies.yml` naming which placement/reuse failure classes are
NOT gateable today (wrong-unit-but-owned, semantic reuse, abstraction) so the injection scope
is documented as correctness-bearing, not "just efficiency." Comments only — no policy
behavior change, no new gate.

## 6. The doctor<->installer marker contract (R5) — CO-DESIGNED NOW (consumed by 1/4)

codex F: sequential, not circular, but the contract must be defined here so 1/4's `doctor`
check isn't retrofitted. Define a single deterministic install-state surface the installer
WRITES and `doctor` READS:

- **Marker location:** `.codas/.install-state.json` — machine-local, MUST NOT enter the
  byte-identical inventory. **codex Q4 BLOCKER:** a dotfile under `.codas/` is NOT reliably
  excluded today — `.gitignore` only covers `.codas/receipts/*.json` + `.codas/cache/`, and the
  non-git scanner fallback `index.py::_IGNORE_PATHS` (line 19) only lists `receipts`+`cache`, and
  `discover_files` surfaces untracked-non-ignored files via `git ls-files --others
  --exclude-standard`. FIX (BEFORE any install code runs): add `.codas/.install-state.json` to
  BOTH `.gitignore` AND `_IGNORE_PATHS`.
- **Schema (codex A2 — expanded; the coarse version would force a doctor retrofit):**
  ```
  {
    "schema_version": 1,
    "git_hooks":  {"pre_commit": {...HookState}, "pre_push": {...HookState}},
    "agent_hooks": {"claude": {"session_start": {...HookState}}},
    "agents_block": "current|stale|absent",
    "claude_shim":  "current|stale|absent"
  }
  // HookState = {status: installed|stale|foreign|skipped|absent,
  //              expected_command, installed_command, settings_path,
  //              marker_id, trusted: true|false|unknown}
  ```
  Per-hook `status` distinguishes installed / stale (marker present, command drifted) / foreign
  (user hook, not trampled) / skipped / absent (mirrors `enforcement.py`'s installed-vs-skipped);
  `trusted` carries the Claude workspace-trust state (installed-but-untrusted is real).
- **Writer:** every installer in this task updates its key (idempotent). **codex A4 hidden dep:**
  because the schema includes `git_hooks`, the EXISTING git-hook installer
  (`enforcement.py::install_hooks`, returns only `InstallResult`, writes no state) must be
  RETROFITTED to write its `git_hooks` key — the schema must not describe state no installer emits.
- **Reader (1/4):** `doctor` adds diagnostics over this surface (hook installed? trusted? block
  fresh?). Until 1/4 ships, `doctor` is unchanged; the marker exists and is correct.
- This task SHIPS the writer + the (expanded) schema; 1/4 ships the reader. The schema is the contract.

## 7. Determinism / §11 / §17 (R6)

- **§17:** core renders deterministically; the hook is a thin "run `codas preflight`, emit
  stdout" shim — NO embedded prompt, NO judgment, Codas spawns no model. Why-prose is advisory,
  labelled, read by no gate.
- **§11:** neutral renders in `app/`; `integrations/` is the only platform-specific code; no
  policy/hash/gate references `.claude/`/platform config. `app/agents_block.py` may import the
  loaders (like `book.py`), never an adapter, never `integrations/`. **codex A3 — call DIRECTION:**
  CLI → app orchestration → `integrations/`; a NEUTRAL renderer must NOT import a platform shim
  (the installer in `integrations/` may call the neutral `app/` renderer to get the block text,
  not the reverse).
- **Determinism:** AGENTS block + CLAUDE shim are deterministic renders, `--verify`'d;
  `.install-state.json` is gitignored (never in the hash); `codas check` 0 + inventory
  byte-identical 2x must hold after install.

## 8. Build order

(1) `app/agents_block.py` renderer + write/verify + register into `--verify` -> (2) policies.yml
ungateable comments + a static policy "what it catches" map -> (3) `preflight --task` digest ->
(4) `integrations/claude.py` shim + SessionStart hook installer + `.install-state.json` writer +
`.gitignore` -> (5) wire `codas hooks --install` / `codas init` to call the platform installer.
Each step deterministic + idempotent; full suite + check 0 + byte-identical + verify after each.

## 9. Open questions — RESOLVED by the codex DESIGN review (see FOLDED section at top)

1. `app/` placement — CONFIRMED correct (loaders OK, no adapter/integrations import).
2. Reuse heuristic — top-level symbols from inventory is enough + deterministic; `impact` is
   over-built; avoid prose/"likely to add" inference (nondeterminism).
3. Verify surface — NEW `codas agents --verify`, NOT extend `codas wiki --verify`.
4. `.install-state.json` — BLOCKER: NOT excluded today; add to `.gitignore` + `_IGNORE_PATHS`
   first (must-hold #1).
5. doc_claims churn — none IF the renderer keeps extension-bearing paths out of backticks/links
   (must-hold #4).

## 10. Acceptance — see prd.md. Make-or-break = R1 (the AGENTS block is a deterministic,
`--verify`'d projection that cannot silently drift) + R6 (determinism/§11/§17 intact).

## 11. AS-BUILT (2026-06-21) — what shipped + deviations

All 4 components + 6 must-holds landed. check 0 · inventory byte-identical 2x · `wiki --verify`
+ `codas agents --verify` clean · 518 tests (18 new in `tests/test_injection.py`).

- **Files:** `app/agents_block.py` (renderer + splice + write/verify), `app/agent_docs.py`
  (app-layer orchestrator for `codas agents`), `integrations/claude.py` (CLAUDE.md shim +
  SessionStart hook), `integrations/install_state.py` (the contract + merge writer), extended
  `app/hooks.py` (agent-injection orchestration), `app/preflight.py` (`_build_digest`),
  `reporting/console.py` (digest render), `cli.py` (`agents` cmd + `hooks --agent-command`),
  `structure/index.py` (BLOCKER#1), `adapters/trellis.py` + `structure/inventory.py`
  (`related_files`), `.codas/policies.yml` (R7 ungateable comment).
- **DEVIATION 1 (digest signal):** the greenlit "affected units from declared scope" had no
  path to bind to — `package` is a coarse label (`null`/`"codas"`, 71/71 tasks) and the task row
  carried no path field. Added `relatedFiles` -> `related_files` to the Trellis adapter + the
  inventory task row (the honest per-task path signal); the digest derives affected_units +
  reuse_candidates + advisory_why from it, degrading to EMPTY deterministically (every task today
  declares none). Fact-stream impact: an always-`[]` field; no book/governance/pack restale (none
  render tasks); byte-identical holds.
- **DEVIATION 2 (must-hold #6):** read as "the git installer EMITS its `git_hooks` slice" —
  `enforcement.install_hooks` calls `_write_git_hook_state`, guarded `if (repo/".codas").is_dir()`
  so a bare non-Codas repo getting only git hooks is never surprised with a marker file.
- **DEVIATION 3 (reuse not reimplement):** promoted the table-cell guard to
  `render_util.guard_table_cell` and refactored BOTH `wiki.py` + `agents_block.py` onto it (the
  first cut tripped `duplicate_implementation` on `_guard_cell` — the exact semantic-reuse miss the
  block preaches); the digest reuses `wiki._owning`/`_owner_index` + `book._read_chapter_prose`
  rather than copying. `wiki.py`'s generated page stays byte-identical (guard is behavior-preserving).
- **Review:** codex MCP was unusable (nested-spawned background tasks, never surfaced content).
  An independent Claude-native adversarial review (cavecrew-reviewer) verified all 7
  correctness invariants (scanner exclusion both paths, doc-claim neutrality, dependency
  direction + no cycle, determinism, JSON idempotence, prefix ownership, no symbol collisions)
  and returned ONE should-nit (unify `ensure_ascii=False` in the install-state writer) — applied.
- **DEFERRED unchanged (per prd):** per-turn hook + `codas status`, Codex/Cursor adapters,
  Layer 3 PreToolUse deny, MCP. The 1/4 doctor reader consumes `read_install_state` (this task
  ships the writer + schema = the contract). CI wiring of `codas agents --verify` rides with 1/4.
</content>
