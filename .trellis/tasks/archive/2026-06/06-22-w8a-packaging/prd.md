# W8a packaging — pip/pipx installable + README quickstart

S1 of the paradigm-onboarding epic (06-21-canonical-layout). Make Codas installable for
cross-repo use so `codas` works on PATH without `PYTHONPATH=src`. Pure packaging — NOT gate-adjacent.

## Done

- **Broaden `requires-python` `>=3.11` → `>=3.9`** (pyproject.toml). Verified-safe: the 563-test
  suite passes on `python3` = 3.9.6; grep confirms no `match`/`case` statements and no runtime
  `X | Y` unions (in isinstance/cast); the 8 modules without `from __future__ import annotations`
  are all 0–6-line `__init__.py` (annotation-free). A lower floor maximizes cross-repo reach.
- **README `## Install` quickstart** — `pipx install codas` (or `pip install codas`) → `codas init`
  → `codas hooks --install` → `codas check .`; notes that the doc's `PYTHONPATH=src python3 -m codas`
  form is source-checkout/dogfood only (an installed `codas` needs no `PYTHONPATH`); flags the
  terminal-state `npx codas` (npm-wrapper-over-binary) as roadmap.

## Acceptance Criteria

- [x] `pip install .` (wheel) into a fresh **python3.9** venv + console script `codas` works with NO
      `PYTHONPATH` (`codas --help` / `codas init` / `codas check`). Also worked on 3.12.
- [x] check 0; inventory byte-identical 2×; 563 tests; agents/wiki `--verify` clean.
- [x] README documents the installed quickstart and marks `PYTHONPATH=src` as source-only.

## Finding (note for the npx/binary roadmap task)

python3.9's bundled pip (21.2.4) rejects `pip install -e .` (PEP 660 editable) with "editable mode
requires a setuptools-based build" — a pip-version artifact, not a Codas issue. The real user paths
(`pipx install codas`, `pip install codas`, `pip install .`) build a wheel and work on 3.9 after a
pip self-upgrade. Document "pipx (recommended) or modern pip"; editable dev install on an ancient
pip needs `pip install --upgrade pip` first.

## Out of scope (later S-tasks of the epic)

- `init` writing policy enablement / honest `none` default + avoid-dup decouple → S2.
- paradigm preset mechanism → S3; role→path mapping → S4; new gate policies → S5/S6 (DESIGN review).
- npx wrapper + PyInstaller binary → roadmap (own task).
