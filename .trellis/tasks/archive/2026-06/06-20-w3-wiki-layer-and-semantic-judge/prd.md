# W3 — wiki layer + the semantic judge tier (post-Block-A roadmap)

## Status
PLANNING UMBRELLA. Records the locked wiki-layer DECISIONS and decomposes the post-Block-A
work into sequenced SLICES, each of which graduates to its OWN start→design→build→codex
review→commit→archive cycle. This task itself authors no code. Builds on the shipped Block A
neutral knowledge tree (`codas wiki --emit-tree`, schema `knowledge_tree/v1`) — its substrate.

## Locked decisions (this session)
1. **Wiki PROSE source = host-agent-direct (primary), NOT CodeWiki.** Producing prose is an
   explicit NON-GOAL to author; the host agent (already an LLM) renders prose over a Codas-fed
   spine. CodeWiki stays an optional, license-gated experiment rail behind the SAME swappable
   corpus contract (deferred; no LICENSE file upstream).
2. **From CodeWiki, BORROW: multi-language extraction + mermaid + html — NOT prose.** These are
   the genuinely reusable parts; the LLM clustering + prose authoring are rejected (non-
   deterministic, trust-free).
3. **Trust TAGS (CONFIRMED/UNCONFIRMED/SEMANTIC) are assigned by a DETERMINISTIC fact-match,
   never by the LLM self-rating** — else LLM-checks-LLM laundering re-enters at the tagging
   boundary. Only the SEMANTIC residue (no fact exists) is irreducibly LLM. (CONTEXT.md
   `## Positioning`, the W3 iron rule.)

## Slices (sequenced; each its own Trellis task when built)

### S1 — mermaid + html views (DETERMINISTIC, no LLM, ship-first quick win)
Pure projections off the already-deterministic `knowledge_tree/v1` + the Atlas pack
`dependency_graph`: a mermaid dependency/containment diagram + a static html/json viewer.
- No LLM, byte-deterministic, printed/emitted OUT of the inventory hash (atlas-pack precedent).
- MUST render the OPEN-WORLD caveat INTO the diagram/html (a dependency graph that hides
  "this is a lower bound, absence ≠ denial" re-imports CodeWiki's false-completeness failure
  at the presentation layer — critic finding). Mirror the note `codas impact` already prints.
- Not gate semantics → no codex DESIGN review required (still full Trellis + codex IMPL review).
- Smallest, cleanest value; recommended FIRST.

### S2 — multi-language extraction (layer-1; BORROW symbols, BUILD resolvers)
The HONEST split (critic correction; matches the perception-model decision record):
- **BORROW** tree-sitter / ctags for the SYMBOL layer per language (cheap, portable, safe).
- **BUILD** the per-language cross-file import/call RESOLVER ourselves — this is the
  load-bearing, NON-borrowable part (resolved cross-file edges are not portable; CodeWiki's
  resolver is non-deterministic — arbitrary cycle-break, eval()-parse — so it is a blueprint,
  NOT a dependency). Normalize every language to the existing resolution-tagged `calls` /
  imports fact shape so policies stay language-agnostic.
- Output stays a sound OPEN-WORLD lower bound; deterministic; **must not** breach the
  pyyaml-only / lightweight-CLI moat lightly (a tree-sitter C-extension dep is a real cost —
  weigh making it an OPTIONAL extra, off the determinism path, gated). Big effort; later.

### S3 — the semantic judge tier (the LLM layer; GATE-ADJACENT)
The fact-bounded LLM seam over the knowledge tree:
- **FEED** — inject the verified `knowledge_tree/v1` spine + an instructions blob as the
  generation grounding (host-agent-direct prose; CodeWiki swappable later).
- **CALIBRATE** — snap each structural claim back to facts and assign a tier DETERMINISTICALLY:
  CONFIRMED (matches a present class-precise fact) / UNCONFIRMED (no match — open-world, read
  as UNKNOWN, never "false") / SEMANTIC (capability/intent label, no fact). Offline tag
  artifact, NOT a `codas check` warning (UNCONFIRMED-as-warning is noisy on lower-bound facts).
- **JUDGE** — on-demand semantic-legality SUGGESTIONS over facts+tree; suggestion-only, NEVER
  committed (preserves byte-identity), MUST ABSTAIN, never upgrades a claim past the facts.
- Unify the corpus-claim reader so W1's `anchor_symbol` becomes the `defines` case; retire/
  delegate `check_code_anchor`.
- **Calibrator + judge are GATE-ADJACENT → a codex DESIGN review is REQUIRED before building
  this slice** (per the iron rule; [[never-skip-trellis-for-low-risk]]).

## Out of scope
- Block B (FSoft CodeWiki shell-out adapter) — separate, license-gated, after S3's swappable
  contract exists.
- Committing any LLM prose into the byte-identical core (forbidden by construction).

## Acceptance (umbrella)
- [ ] The three slices are recorded with their determinism / gate / sequence properties.
- [ ] S1/S2 carry the open-world caveat into their output; S3's tags are deterministic.
- [ ] Each slice, when built, goes through full Trellis; S3 additionally through codex DESIGN
      review first.

## Suggested sequence
S1 (deterministic quick win) → S3 seam with host-agent-direct stub (the real Codas value) →
S2 (multi-lang, big) → Block B (optional, license-gated). S2 and Block B may never ship.
