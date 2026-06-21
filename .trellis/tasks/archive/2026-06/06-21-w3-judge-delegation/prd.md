# W3 judge delegation to a cheap sub-agent — mechanisms brainstorm

## Status
PLANNING / BRAINSTORM. Explore the mechanism space, decide a layered design, THEN build later
through the full Trellis rhythm. No implementation in this task beyond the recorded design.

## Problem / insight
The W3 semantic loop's LLM steps — AUTHOR (write the corpus prose) and JUDGE (reason over
facts+tree+tiers) — often run on the EXPENSIVE main agent and POLLUTE its context (the feed is
8000+ lines). They should be delegated to a CHEAP, disposable sub-agent: the main agent only
orchestrates the deterministic FEED / CALIBRATE and collects the final suggestions.

The load-bearing insight: **a cheap/weak model is SAFE here precisely because of the
fact-anchoring.** Its hallucinated node-ids surface as UNCONFIRMED; it cannot launder a false
concept past STRUCTURE_CONFIRMED (which confirms only the tuple, never the concept). The
deterministic calibration substitutes for model capability — "cheap-but-disciplined" beats
"expensive-but-ungrounded". This is Codas's agent-agnosticism paying off.

## The brainstorm question
By what MECHANISMS does Codas enable / encourage delegating the W3 judge to a cheap sub-agent —
beyond the passive CONTRACT.md recommendation? Candidates to explore + weigh:
1. **Contract/docs** — recommend the delegation pattern (passive; already partly in CONTRACT.md).
2. **CLI dispatch seam** — Codas emits STRUCTURED delegatable work (per-subsystem feed slices +
   a judge-prompt template + the calibration) that ANY harness consumes to spawn cheap agents.
   Codas prepares; the harness dispatches. (e.g. `--emit-feed --scope <package>`; a dispatch
   manifest.)
3. **Hooks** — a Codas hook (it already has a hook system for check-gating + `hooks --install`)
   that wires the delegation inside a SPECIFIC host harness, kept OUT of core (a reference
   integration).
4. **Agent-spec** — ship a reusable sub-agent DEFINITION ("codas-semantic-judge") a
   Claude-Code-style harness dispatches; Codas provides the spec, the harness runs it.
5. **MCP** — an MCP tool exposing feed+calibrate (NOTE: MCP was vetoed for the wiki; include
   only to reject explicitly).

## Hard constraints (the design must respect)
- Codas stays **agent-AGNOSTIC**: it must NOT embed a specific agent harness or assume a model.
- **§17 no-LLM-in-core**: Codas core must NOT spawn or invoke an LLM. Orchestration + dispatch
  live OUTSIDE the core; Codas at most provides a SEAM (structured artifacts / a documented
  contract / an optional reference hook off the determinism path).
- **Determinism**: any new Codas surface is a deterministic projection, out of the inventory hash.
- Don't spend the lightweight-CLI moat (no heavy deps, no server).

## Deliverable (this task)
A brainstormed, adversarially-reviewed DESIGN: which mechanism(s) Codas provides (the seam) vs
what stays in the harness vs what is just documented; the layered recommendation; and the honest
verdict (is any of this worth building now, given W3 has no external adoption yet?).
