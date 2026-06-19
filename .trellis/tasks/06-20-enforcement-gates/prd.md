# P6 enforcement gates: GitHub Action + git hook installer

## Goal

Deliver P6's exit criterion — "Codas can block a bad PR or commit with evidence-backed
findings" — via two enforcement integrations backed by `src/codas/integrations/` (the
`role-integrations` structure unit, currently `planned`, flipped `active`):

1. **GitHub Action CI gate** — a committed `.github/workflows/codas.yml` that runs the
   bootstrap test gate + `codas check` on push / pull_request, so a bad change fails CI.
   Dogfood-safe (runs in CI, not on local commits, so it never blocks the maintainer's
   own `PYTHONPATH=src` workflow).
2. **git hook installer** — `codas hooks --install` writes `pre-commit` / `pre-push`
   hooks (under `.git/hooks/`, or a configured hooks dir) that run `codas check`,
   blocking a commit/push on error findings. Backed by a pure render module so the hook
   bodies are testable. NOT auto-applied to this repo (codas isn't on PATH here; the
   Action is the self-gate).

## Requirements

- `src/codas/integrations/__init__.py` + `git_hooks.py`:
  - `render_hook(hook_name, command="codas check .") -> str` — pure POSIX-sh hook body
    with a Codas marker line (so the installer can recognize/refresh its own hook and
    refuse to clobber a foreign one).
  - `install_hooks(repo, *, force=False, command=...) -> InstallResult` — writes
    `pre-commit` + `pre-push` to the repo's git hooks dir (honor `core.hooksPath`,
    else `.git/hooks`), `chmod +x`; skips (without `force`) a hook that exists and is
    NOT Codas-marked (don't trample a user's hook); idempotent for its own.
  - `github_workflow.py::render_workflow() -> str` — pure `.github/workflows/codas.yml`
    body (checkout, setup-python, run bootstrap gate + `codas check`). Deterministic.
- CLI: `codas hooks [--install] [--force]` (and print the rendered workflow path / hint).
  Exit 0 on success; clear message if not a git repo.
- Commit `.github/workflows/codas.yml` (rendered) so the CI gate is live for this repo.
- Flip `role-integrations` unit `status: planned -> active` in `.codas/structure.yml`
  (it now exists). Keep `codas check .` = 0.

## Acceptance Criteria

- [ ] `.github/workflows/codas.yml` present; runs tests + `codas check` on push/PR.
- [ ] `codas hooks --install` in a temp git repo writes executable pre-commit + pre-push
      that invoke `codas check`; re-run is idempotent; a foreign existing hook is skipped
      without `--force`. Fixtures prove all three.
- [ ] `render_hook` / `render_workflow` deterministic (byte-identical across calls).
- [ ] `role-integrations` unit active + present; `codas check .` = 0; inventory
      byte-identical; full suite green; `wiki --verify` clean.
- [ ] §11 (integrations module imports no policy/adapter for its render/install; it shells
      out to `codas check`, never imports the engine) / §17 (no LLM) clean.

## Implemented (2026-06-20) + codex impl review folded

Shipped `integrations/enforcement.py` (render_hook/render_workflow/install_hooks),
`app/hooks.py` (the codas-app bridge — the boundary forbids `codas-source` from
`role-integrations`, so the CLI routes through app), `codas hooks --install [--force]
[--command]`, committed `.github/workflows/codas.yml` (== render_workflow()), and
flipped `role-integrations` active. 302 tests; check 0; inventory byte-identical;
`wiki --verify` clean (governance.md regenerated for the unit change).

Codex impl review — **0 BLOCKERs**, all 4 SHOULDs + NIT folded:
- Relative `core.hooksPath` resolved against the **worktree root** (where Git runs it),
  not the invocation dir (`_worktree_root`).
- Strict Codas-hook recognition: marker must be on **line 2** (`_is_codas_hook`), so a
  foreign hook merely mentioning the marker is never clobbered.
- File-valued `core.hooksPath` (e.g. `/dev/null`) / bare repo → controlled `None`
  (clean CLI failure), not an `mkdir` crash.
- `--command` override (CLI + app + render) for the PATH footgun (below); idempotent
  reinstall is now a true no-op (no rewrite/chmod when the body is unchanged).

**PATH footgun (documented):** installed hooks run `codas check .`, which assumes
`codas` is on PATH (the pip console script). In a source checkout (this repo runs
`PYTHONPATH=src python3 -m codas`), install with
`--command 'PYTHONPATH=src python3 -m codas check .'`. This repo deliberately does NOT
self-install the hooks (the GitHub Action is the self-gate), so a maintainer's commits
are never blocked by a missing-PATH `codas`.

## Out of scope

- `codas init` (`.codas` scaffold) — next P6 slice.
- Trellis-native hooks + a published PyPI package (the Action uses the repo's
  `PYTHONPATH=src` form for dogfood; generic `pip install codas` packaging is later).
- pre-merge / branch-protection config (documented, not scripted).
