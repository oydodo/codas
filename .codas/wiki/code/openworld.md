# Code-wiki: the open-world invariant

> An Atlas **code-wiki** page (W1). The prose below is **advisory** — Codas does NOT verify
> its meaning. Only the `anchor_symbol` claims in the `atlas:claims` block are verified
> (each must resolve to a current symbol fact). This page doubles as agent-readable context
> for the open-world model.

## What this is

Codas's facts are a **sound lower bound**, not a complete set. A static call/symbol/import
extractor emits only what it resolves and drops the rest, so a **positive** reading is
reliable ("A calls B" is real) but **absence is not evidence** (completeness over runtime
behaviour is undecidable — Rice). Config/declared facts are closed-world (read in full, so
absence IS evidence). The model lives in code at `open_world_gaps` + the `OPEN_WORLD_GAPS`
manifest, and is consumed today by `codas impact` (which stamps its result a lower bound).

## Why it matters

Two consumers depend on it: deterministic policies never gate on the *absence* of an
open-world fact (hence no "dead code" gate), and a reasoner (today `codas impact`; later an
LLM judge) reads absence as *unknown*, not denial. This very code-wiki obeys it: a
non-resolving `anchor_symbol` is a **warning**, never a hard error.

<!-- The verified surface: each anchor asserts a concept is defined by a symbol that must
     exist in the current symbol facts. A rename/move of any of these without updating this
     page makes the anchor stop resolving -> a code_anchor warning (the code->doc drift catch). -->
```atlas:claims
anchor_symbol: open-world gap manifest -> src/codas/facts/openworld.py:open_world_gaps
anchor_symbol: reverse-reachability impact (open-world consumer) -> src/codas/app/impact.py:compute_impact
anchor_symbol: the code-wiki anchor verifier -> src/codas/policies/code_anchor.py:check_code_anchor
```
