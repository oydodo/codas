# tree-sitter gate adapter (per-language symbols/imports)

For a language you want to GATE (e.g. Swift for the ciri repo), a deterministic in-core
tree-sitter extractor for **symbols + imports** (the EASY layer-2 part; NOT the call-resolver).
These feed the gate (ownership / duplicate / dependency-direction) per-language.

Context + reasoning: `docs/codas-architecture-decisions.md` §1/§2 (committed `c656b0b`).
Source dialogue: handoff `.trellis/workspace/oydodo/handoff-2026-06-23-four-tasks.md` task ③.
Reusable design: `.trellis/tasks/archive/2026-06/06-22-swift-extraction/design.md` (Swift was
the worked example; codex review B1/B2/B3 already folded).

## Why tree-sitter here, not CodeGraph

The gate needs determinism. tree-sitter in-process is inherently deterministic (like `ast`).
CodeGraph (non-deterministic, external) stays advisory (task ②). Calls are mostly advisory →
DEFER the per-language call-resolver; ship only symbols + imports, which are the gate-grade,
language-internal facts.

## Requirements

- Optional extra `codas[swift]` (`tree-sitter~=0.23, tree-sitter-swift~=0.7`) — Python core
  stays pyyaml-only.
- `adapters/<lang>_parse.py` + `adapters/<lang>.py` (`extract_<lang>_symbols/imports`).
- `facts/languages.py` light registry mapping extension → extractor.
- `ScanContext.symbols()/imports()` additive merge with **early-return on empty extra** →
  byte-identical for Python-only repos (the identity guarantee).
- Calls DEFERRED (advisory via CodeGraph, task ②).
- Fixtures via `tmp_path`, NEVER committed under a scanned root (codex review B1).

## Acceptance Criteria

- [ ] A Swift file's top-level symbols + imports appear in facts and feed ownership / duplicate
      / dependency-direction gates.
- [ ] Python-only repo with no language extra installed → byte-identical, gate unchanged
      (early-return identity test).
- [ ] The optional extra installs uniformly across envs (codex review B2).
- [ ] `PYTHONPATH=src python3 -m codas check .` → 0 findings; tests green; byte-identical.

## Notes

- gate-semantics (touches fact extraction) → **codex DESIGN review BEFORE impl** — though most
  of the design is already in the archived swift-extraction design. codex-MCP stalls →
  Claude-native adversarial reviewer.
- Effort ~1-2 days per language.
- Key files: `adapters/`, `facts/languages.py`, `facts/context.py` (merge seam).
