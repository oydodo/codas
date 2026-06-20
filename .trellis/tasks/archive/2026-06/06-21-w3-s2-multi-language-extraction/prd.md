# W3·S2 — multi-language extraction (borrow tree-sitter symbols, build resolvers)

## Status
PLANNING. Child of `06-20-w3-wiki-layer-and-semantic-judge`. THIRD/LAST in sequence; biggest
effort; MAY NEVER SHIP (weigh against the moat). DETERMINISTIC, no LLM. The "borrow CodeWiki's
multi-language" decision, with the HONEST split the critic enforced.

## Goal
Extend Codas's facts beyond Python so the knowledge tree / call graph / policies work on
multi-language repos — without breaking determinism or the lightweight-CLI moat.

## The honest split (critic correction; matches the perception-model decision record)
- **BORROW** tree-sitter / ctags for the per-language SYMBOL layer (cheap, portable, safe).
- **BUILD** the per-language cross-file import/call RESOLVER ourselves — the load-bearing,
  NON-borrowable part. Resolved cross-file edges are not portable; CodeWiki's resolver is
  non-deterministic (arbitrary cycle-break, eval()-parse) so it is a BLUEPRINT, not a dependency.
  This is net-new engineering, NOT a borrow — say so plainly.
- Normalize every language to the EXISTING resolution-tagged `calls` / imports fact shape so all
  policies stay language-agnostic (the fact vocabulary is already language-neutral).
- Output stays a sound OPEN-WORLD lower bound; deterministic; per-§11 a language adapter.

## Moat constraint (critic finding — load-bearing)
A tree-sitter C-extension breaks the pyyaml-only / pip-installable / serverless invariant that IS
Codas's moat vs SonarQube. Therefore: make multi-language an **OPTIONAL extra**, OFF the
determinism path, gated — never a default dependency. If it cannot be done without spending the
moat, it stays unbuilt. This slice is explicitly allowed to be DEFERRED INDEFINITELY.

## Out of scope
- S3 (judge), S1 (mermaid/html), Block B.
- Any non-deterministic extractor (the pyan lesson: cross-process nondeterminism disqualifies).

## Acceptance
- [ ] Symbol extraction borrowed per language; import/call resolver built deterministically.
- [ ] All languages normalize to the existing `calls`/imports fact shape; policies unchanged.
- [ ] Determinism preserved (byte-identical across processes); open-world lower bound preserved.
- [ ] The extra is optional/gated; the pyyaml-only default install is NOT changed.
- [ ] `codas check .` 0; full suite green.

## Open questions (for a later design pass)
- tree-sitter vs ctags vs stack-graphs/SCIP as the symbol source (determinism + install footprint).
- Whether the resolver is per-language modules or one normalized engine with per-language frontends.
- Whether the cost is ever justified vs staying Python-first (demand-driven).
