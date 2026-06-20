# W3·S1 — mermaid + html deterministic views off knowledge_tree

## Status
PLANNING. Child of `06-20-w3-wiki-layer-and-semantic-judge`. SECOND in sequence (after S3).
DETERMINISTIC, no LLM, NOT gate semantics → no codex DESIGN review required (still full Trellis
+ codex IMPL review). The "borrow CodeWiki's mermaid + html" decision, done the Codas way:
fact-driven pure projections, not LLM-rendered.

## Goal
Human/agent-navigable views of the verified structure, derived purely from the shipped Block A
`knowledge_tree/v1` + the Atlas pack `dependency_graph`. Capture CodeWiki's "description" value
WITHOUT its trust cost (no LLM, no non-determinism).

## Requirements
- A **mermaid** diagram emitter (dependency / containment graph) — a pure projection of the
  knowledge tree / dependency graph. Deterministic (sorted nodes/edges), byte-stable, printed
  OUT of the inventory hash (atlas-pack precedent). Likely a `codas wiki --emit-*` sibling.
- A static **html/json viewer** over the same facts (navigable tree + ownership + call adjacency).
  Deterministic; out of hash.
- **OPEN-WORLD caveat rendered INTO the diagram/html** (critic finding): a dependency graph that
  hides "this is a sound lower bound — absence ≠ denial" re-imports CodeWiki's false-completeness
  failure at the presentation layer. Mirror the open-world note `codas impact` already prints.
- §11/§17 clean; pure projection of the inventory/derived views; no LLM; no new fact extraction.
- Fixture-pinned bytes (run-twice byte-identical), mirroring tests/test_knowledge_tree.py.

## Out of scope
- S3 (judge tier), S2 (multi-lang), Block B.
- Any LLM rendering of the diagram/prose.

## Acceptance
- [ ] mermaid + html/json emitters are pure deterministic projections, byte-stable (fixture-pinned).
- [ ] The open-world lower-bound caveat is visible in the rendered output.
- [ ] Out of the inventory hash; `codas check .` 0; full suite green; wiki --verify clean.
- [ ] No LLM; §11/§17 clean.
