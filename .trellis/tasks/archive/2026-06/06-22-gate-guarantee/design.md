# Design — Gate-guarantee (gaps 1/4)

Concrete change map. Gate-adjacent (doctor warn semantics + committed CI artifact) → build to
this after an adversarial DESIGN review.

## 0. Principle: doctor diagnoses, the gate enforces

doctor is a READ-ONLY diagnostic. It must SEE the gate/injection state but must not BE the gate:
- absent hooks → WARN, never fail (git hooks do not travel with a clone; a fresh clone with no
  hooks is normal, and CI gates regardless of local hooks).
- stale AGENTS block / wiki book → doctor WARNS; the real freshness gate is the CI `--verify`
  (R4). doctor never auto-installs/writes (stays read-only); it SUGGESTS the fix command.

So: doctor's exit code is unchanged (fail only on the existing required-input failures). The new
diagnostics are pure visibility.

## 1. Live-probe helpers (integrations, NEW public)

Live state is ground truth (install-state can be stale if a user removed a hook post-install), so
doctor LIVE-PROBES the files; it reads install-state only for `trusted` (unprobeable).

- `enforcement.git_hook_status(repo) -> dict[str, str]` — `{ "pre-commit": s, "pre-push": s }`,
  `s ∈ installed | foreign | absent`. Reuses `_hooks_dir` (honors core.hooksPath) + `_is_codas_hook`.
  No usable hooks dir (non-git) → both `absent`.
- `claude.session_hook_status(repo) -> str` — `installed | absent | malformed`, by loading
  `.claude/settings.json` and scanning `hooks.SessionStart` groups with the existing `_is_ours`.
  Missing file → `absent`; unparseable → `malformed`.

Both are pure read-only probes (no mutation), mirror the install logic so detection cannot fork.

## 2. doctor diagnostics (app/doctor.py)

Append four WARN-capable diagnostics (after `_trellis_context`, before `_legacy_prototype` so the
fixed deterministic order is stable):

- `git_hooks` — from `git_hook_status`: both installed → ok "pre-commit + pre-push installed";
  any absent → warn "<names> not installed — run `codas hooks --install`"; any foreign → warn
  "<name> is a non-Codas hook (pass --force to overwrite)".
- `agent_hook` — from `session_hook_status` + `read_install_state` trusted: installed → ok, but
  if trusted != true append " (approve workspace-trust in Claude Code)"; absent → warn "SessionStart
  hook not installed — run `codas hooks --install`"; malformed → warn.
- `agents_block` — `verify_agents_block(repo)`: file present + empty stale list → ok; AGENTS.md
  absent → warn "AGENTS.md missing — run `codas agents --write`"; stale → warn "AGENTS.md Codas
  block stale — run `codas agents --write`". (Wrap in try/except ConfigLoadError/StructureMapError
  → warn "cannot render (config/structure not loadable)", never crash — mirrors hooks.py.)
- `claude_shim` — `verify_claude_shim(repo)`: ok / absent-warn / stale-warn.

§11/§17: doctor (codas-app) imports `enforcement`/`claude`/`install_state` (role-integrations —
codas-app MAY depend on it; only codas-source/cli may not) and `agents_block`/`claude` verify (app);
no LLM, no adapter, deterministic fixed order. Update the doctor docstring (it currently says
"imports loaders only").

## 3. CI freshness wiring (enforcement.render_workflow)

Add two steps after the existing "Codas check":
```
      - name: Codas agents verify
        run: PYTHONPATH=src python -m codas agents --verify .
      - name: Codas wiki verify
        run: PYTHONPATH=src python -m codas wiki --verify .
```
Deterministic, no timestamp. Regenerate the committed `.github/workflows/codas.yml` to match
`render_workflow()` exactly (it is hand-synced today — render_workflow is referenced only by a
test). Update `tests/test_enforcement.py` to assert the two verify steps are present.

NB local git hooks stay `codas check` only (fast per-commit); the freshness `--verify`s live in CI
(less frequent, the right place for a render-drift gate). Not adding verify to pre-commit/pre-push.

## 4. Build order

(1) `enforcement.git_hook_status` + `claude.session_hook_status` (+ tiny unit tests) →
(2) doctor diagnostics + docstring → (3) render_workflow verify steps + regenerate committed
workflow + test → (4) gauntlet (check 0, byte-identical, wiki/agents --verify, full suite) →
(5) IMPL review → commit/archive.

## 5. Risks / review focus

- doctor importing role-integrations: allowed by dependency_rules (codas-app has no
  must_not_depend_on role-integrations), but confirm `codas check` dependency_direction stays 0.
- WARN-not-fail: confirm `doctor_has_failures` still only trips on the existing required-input
  fails, so a fresh clone (no hooks) exits 0 with warnings — does NOT break CI's `codas doctor` if
  any step runs it. (CI runs check/verify, not doctor, so no exit-code coupling — confirm.)
- The committed `.github/workflows/codas.yml` must byte-match `render_workflow()` after the edit
  (no `--verify` enforces this yet — manual sync + the test is the only guard; call it out).
- Determinism: doctor reads `.install-state.json` (gitignored, machine-local) — its presence/
  absence must NOT affect `codas check`/inventory (BLOCKER#1 already excludes it; re-confirm).

## 6. FOLDED design-review changes (APPROVE-WITH-CHANGES — build to these)

Independent adversarial DESIGN review (codex MCP unusable). §11 + no-cycle CONFIRMED. Folds:

1. **Catch-all, never crash (MUST).** The `agents_block`/`claude_shim` freshness probes wrap the
   verify call in `except Exception` (not just ConfigLoadError/StructureMapError) → warn with the
   error, never a traceback (broadens the hooks.py `_doc_freshness` precedent; covers a disk/
   permission read error too).
2. **WARN stays; CI `--verify` IS the staleness gate (SHOULD).** doctor stays read-only/WARN
   (the read-only principle holds); the binding staleness GATE is the R4 CI `agents --verify` +
   `wiki --verify` steps — they are load-bearing, not optional. Documented here; the committed-
   workflow-drift risk (someone deletes the steps) is the pre-existing un-gated-workflow gap below.
3. **Reconcile live-probe vs install-state (SHOULD).** When a hook is LIVE-absent but
   `.install-state.json` recorded it `installed`, the detail says so (e.g. "pre-commit absent
   (recorded installed; file removed)") — the payoff of holding both signals; catches a manual
   post-install deletion.

PRE-EXISTING (noted, NOT fixed here): committed `.github/workflows/codas.yml` has no `--verify`
drift gate (a future `codas enforcement --verify`); `integrations/claude.py` imports
`app/agents_block` for `splice_managed_block` (thin-shim smell; no cycle — agents_block imports no
integration; a future move to a neutral `render`-util would clean it).
