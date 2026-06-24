# Implementation Plan — tree-sitter gate adapter

## Scope
Implement reviewed design for task `06-23-tree-sitter-gate-adapter`: add gate-grade Swift symbol/import extraction through tree-sitter, keep Python extraction unchanged, and make `fact_delta` symmetric by parsing registered language facts on both working-tree and HEAD sides.

## Steps
1. Add optional Swift dependencies in `pyproject.toml` without changing core Python floor or core dependency set.
2. Add Swift parse/extract adapters:
   - content-first parser for git blobs and disk wrapper for working tree;
   - symbols for class/struct/enum/actor/protocol/function/typealias;
   - exclude extensions;
   - imports with `target_path=None`.
3. Add non-Python language registry for gate-grade extractors.
4. Add neutral merge helpers for symbol/import/snapshot facts so `ScanContext` and `head_snapshot` share one path without reverse dependencies.
5. Generalize `list_python_paths_at_head` to `list_paths_at_head(repo, extensions)` while keeping Python wrapper.
6. Update `head_snapshot` to list registered source extensions, route blobs by extension, parse Swift from content, and merge language facts symmetrically with Python facts.
7. Add tests for graceful degrade, Swift extraction, extension exclusion, deterministic merge, HEAD extension filtering, and Swift working/HEAD delta symmetry.
8. Verify core suite without Swift extra, then Python 3.12 + Swift extra suite/check/wiki/agents when available.

## Guardrails
- No committed `.swift` fixture files; use temporary directories only.
- No Swift call edges in this task.
- No CodeGraph dependency or advisory facts in this task.
- No whole-project Python floor bump.
- No helper placement that makes `snapshot.py` import `context.py`.
