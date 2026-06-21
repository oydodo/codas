# Design — W3 judge delegation (brainstorm outcome; DOCS-ONLY now)

Outcome of a 7-agent brainstorm (5 mechanism lenses → synthesis → adversarial critique,
workflow wnvoui4lv). The critique sharpened the synthesis materially: it had over-committed to
building a `--scope` primitive on an UNMEASURED premise. Measured here → docs-only now.

## The converged decision
**Delegation is 100% achievable TODAY with ZERO core change.** Codas core spawns no LLM (it
shells only git); the AUTHOR/JUDGE corpus lives in the gitignored `.codas/cache/semantic/`
outside core; a harness can already spawn a cheap disposable sub-agent that shells the existing
`codas wiki --emit-feed` / `--calibrate`. The cheap-agent SAFETY is intrinsic to `tier()` (a weak
model's hallucinated node → UNCONFIRMED; a false concept on a real tuple stays
STRUCTURE_CONFIRMED-but-flaggable) and owes nothing to who runs the LLM. The main-context
pollution the goal targets is solved ENTIRELY by the sub-agent boundary — a pure harness concern.

### Lens verdicts
- contract-docs → DOCS-ONLY (the floor; §17-safe, zero-moat-cost).
- cli-dispatch-seam → BUILD `--scope` (narrow) — but the critic downgraded this (see below).
- hooks → DOCS-ONLY (a reference recipe; never ship an agent-spawning hook body — embeds a
  harness/model assumption, spends agnosticism).
- agent-spec → DOCS-ONLY now (point at the existing iron rules; no vendor subagent file in core).
- mcp → REJECT (relocates only transport, spawns no LLM either way, spends the moat on a daemon).

## NOW — the only action (docs-only)
Add a SHORT, model-NEUTRAL delegation note to CONTRACT.md `## The W3 semantic judge loop`:
dispatch AUTHOR + JUDGE to a cheap disposable sub-agent; the main agent runs only the
deterministic FEED/CALIBRATE and merges the suggestion-only output; cheapness is SAFE because
`tier()` catches a weak model's errors (the fact-anchoring rationale). **REFERENCE the iron rules
already in the JUDGE step — do NOT mint a second "Semantic Judge Domain Role" doc** (a restatement
duplicates the single source of truth and invites spec_drift — the project's recurring failure).

## MEASURED — why `--scope` is NOT load-bearing now
`codas wiki --emit-feed` = 8130 lines / 267 KB ≈ **67k tokens** — fits a cheap model's ~200k
context with large headroom. So the disposable sub-agent can hold the WHOLE feed; the "context
bomb" is the MAIN agent's problem, already solved by the sub-agent boundary at zero core cost.
The contract ALREADY mandates per-package work in prose ("work one subsystem at a time"). So
mechanical slicing is at most an ergonomic helper, not the load-bearing primitive the synthesis
claimed.

## DEFER `--scope <node-id>` until DEMONSTRATED friction
Build the children-closure slice (`--scope` on `--emit-feed`/`--calibrate`) ONLY IF a real
delegated run shows hand-slicing is the actual pain AND a cheap agent genuinely can't hold the
feed. If ever built, the HARD determinism rule the synthesis under-specified:
- `--scope` filters which CLAIMS are tiered (by SUBJECT-node membership in the closure), and
  tiers each against the **FULL** `node_ids`/`calls_index` — the closure selects WORK, never the
  fact universe. Else a cross-package `calls` claim flips STRUCTURE_CONFIRMED→UNCONFIRMED purely
  by slice boundary and per-claim tiers become scope-dependent (union-of-slices != whole at the
  TIER level). Empty closure → a valid empty slice (total function). Property tests REQUIRED
  (union==whole at feed AND tier level; scope-invariant per-claim tiers).

## REJECT (not defer — "defer" implies a roadmap these don't deserve)
- `--emit-dispatch` manifest — a harness computes it in ~4 lines over `--emit-tree` package nodes;
  a schema is a permanent maintenance + byte-identity tax for an absent consumer.
- A duplicate "Semantic Judge Domain Role" doc — the iron rules live in CONTRACT.md already; a
  pointer, never a restatement.
- Any Codas-authored subagent file or delegation-hook BODY — naming `claude -p`/`codex exec` is
  agnosticism spend even outside `src/`. A harness author's job, not Codas's.
- MCP for this use.

## §17 invariant — restated precisely (critic correction)
Core is NOT subprocess-free: it shells `git` in 4 modules (git.py, structure/index.py,
integrations/enforcement.py, app/doctor.py). The real invariant: **core may shell ONLY
deterministic, content-addressed tools (git); it must NEVER shell a model or any nondeterministic
process.** That is the §17 test every future seam is measured against — and the rule that forbids
a `--run`/runner directive ever entering core (the git precedent leaves the door ajar).

## Acceptance
- [ ] CONTRACT.md gains the model-neutral cheap-sub-agent delegation note (references, does not
      duplicate, the iron rules).
- [ ] `--scope`, `--emit-dispatch`, a Domain Role doc, a subagent/hook artifact, MCP = NOT built.
- [ ] check 0; tests green; byte-identical; verify clean. No core code change.
