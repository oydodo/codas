# W3·S3 — semantic judge tier (feed + deterministic-tag calibrate + suggestion-only judge)

## Status
PLANNING. Child of `06-20-w3-wiki-layer-and-semantic-judge`. **FIRST in sequence** (user
chose S3 → S1 → S2). The LLM semantic tier over the shipped Block A knowledge tree — the real
Codas value at the wiki layer. **GATE-ADJACENT: a codex DESIGN review is REQUIRED before any
build** (the calibrator/judge touch how claims are verified), per [[never-skip-trellis-for-low-risk]].

## Goal
The fact-bounded LLM seam: ground prose generation in verified facts, snap the output back to
facts with DETERMINISTIC trust tiers, and expose semantic-legality suggestions that can never
masquerade as ground truth. prose source = host-agent-direct (CodeWiki swappable later, Block B).

## Requirements
- **FEED** — emit the Block A `knowledge_tree/v1` spine + an instructions blob as the
  generation grounding (a CLI surface, e.g. an emit that a host agent consumes). Deterministic,
  out of the inventory hash. No LLM in this step.
- **CALIBRATE** — snap each structural claim in the generated corpus back to facts and assign a
  tier **DETERMINISTICALLY** (machine fact-match, NEVER the LLM self-rating — the W3 iron rule;
  else LLM-checks-LLM re-enters at the tagging boundary):
  - CONFIRMED — matches a present class-precise fact (symbol/import/call exists).
  - UNCONFIRMED — no matching fact: open-world, read as UNKNOWN, **never "false"** (absence ≠ denial).
  - SEMANTIC — capability/intent label with no expressible fact: irreducibly LLM, a hypothesis.
  Output = an OFFLINE tag artifact, **NOT a `codas check` warning** (UNCONFIRMED-as-warning is
  noisy on open-world lower-bound facts).
- **JUDGE** — on-demand semantic-legality SUGGESTIONS over facts+tree; suggestion-only, NEVER
  committed (preserves byte-identity), MUST ABSTAIN when unsure, never upgrades a claim past the
  facts.
- **Unify the corpus-claim reader**: W1's `anchor_symbol` becomes the `defines` case; retire or
  delegate `check_code_anchor`.
- §17/§11 clean: the deterministic core (feed + the fact-match that assigns tags) stays LLM-free;
  the LLM is strictly a generation/judge client whose output is a claim, off the determinism path.

## Out of scope
- S1 (mermaid/html), S2 (multi-lang), Block B (CodeWiki shell-out).
- Committing any LLM prose into the byte-identical inventory.

## Acceptance
- [ ] codex DESIGN review run + folded BEFORE implementation.
- [ ] Tags assigned by deterministic fact-match (a test proves the LLM cannot set the tier).
- [ ] CONFIRMED/UNCONFIRMED/SEMANTIC semantics enforced; UNCONFIRMED never reported as a violation.
- [ ] Judge output never committed; core stays byte-identical; `codas check .` 0; full suite green.

## Open design questions (for the codex DESIGN review)
- Where the corpus + tags live (`.codas/wiki/...` out-of-hash vs an offline artifact).
- The exact fact-match grammar for CONFIRMED (reuse the Block A node-id `<path>::<class>::<symbol>`).
- Whether the judge is a CLI subcommand, an MCP surface, or a host-agent contract only.
- How `check_code_anchor` / W1 `anchor_symbol` fold into the unified `defines` reader.
