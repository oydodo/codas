# Design — Atlas code-wiki anchor verifier (W1, all-open)

## Placement + hash isolation
- LLM-wiki pages live under `.codas/wiki/code/` (committed).
- Exclude `.codas/wiki/code/` from the inventory-ingested prose streams so its prose
  (path refs WITH line numbers) never enters the byte-identical hash:
  - markdown adapter: add `.codas/wiki/code/` to SKIP_PREFIXES (doc_claims skips it).
  - wiki adapter extract_wiki_claims: skip files under `.codas/wiki/code/`.
- The code-anchor claims are read separately as a POLICY-TIME fact, POSITION-STRIPPED
  (identity = (kind, subject, value); line kept only for human evidence display, NOT in
  any inventory-serialized structure) -> not in inventory -> no hash dependence on prose.

## Grammar (extend the atlas:claims block)
Inside a ```atlas:claims fence (the same fence extract_generated_claims reads), a new line:
  anchor_symbol: <concept> -> <path>:<name>
e.g.  anchor_symbol: open-world invariant -> src/codas/facts/openworld.py:open_world_gaps
Parsed by a new `extract_code_anchor_claims(repo, files, code_root=".codas/wiki/code")`
mirroring extract_generated_claims (fence-aware; `<kind>: <subject> -> <value>` shape;
value split on the LAST ':' into (path, name)). Deterministic (pages sorted, claims in
file order). New dataclasses CodeAnchorClaim{source, line, concept, path, name} +
CodeAnchorClaims. Re-exported via codas.facts.context __all__.

## ScanContext seam
`ScanContext.code_anchor_claims() -> CodeAnchorClaims` (memoized; reads the code_root;
policy-time, NOT serialized into inventory — like generated_claims()).

## Verifier policy (the gate, warning severity)
`policies/code_anchor.py::check_code_anchor(ctx) -> list[Finding]`:
- for each anchor, resolve against ctx.symbols(): exists a SymbolFact with module==path AND
  name==name?
- RESOLVES -> nothing.
- DOES NOT RESOLVE -> WARNING (never error — ALL-OPEN), message names the page + the
  anchor + carries the open-world caveat ("calls/symbols are open-world; this anchor may
  not resolve because the code moved (update the wiki) OR uses a dynamic/conditional form
  the extractor misses — a lower bound, verify by hand"). Evidence = the wiki page + line.
- §11-clean: imports core.models + facts.context only (no adapter). Consumes facts via ctx.
- Wire check.py (Nth ctx consumer -> orchestration monkeypatch updated). Declare
  policies.yml (severity warning). policy_registry stays consistent.

## Open-world handling (deferred world-split = ALL-OPEN)
Every anchor non-resolution is treated open-world -> warning. No closed-world hard-error
path in this slice. (The later optimization: a top-level-def anchor that the symbols family
DOES enumerate but is now absent = closed-world-decidable -> could be an error. Not now.)

## Dogfood page
Hand-author `.codas/wiki/code/openworld.md`: prose describing the open-world invariant +
an atlas:claims block with anchor_symbol lines pointing at real openworld.py symbols
(open_world_gaps). Anchors resolve -> check 0. (This is the manual host-agent "generation"
— the generator is the host agent, per §17.)

## Determinism / §17 / §11
- code_anchor claims NOT in inventory -> byte-identical inventory unaffected by the wiki.
- Verifier deterministic (sorted findings). No LLM in the core (the page is hand/agent
  authored OUTSIDE Codas; Codas only reads + resolves anchors).
- The wiki is NOT a generated/ page -> never touches verify_generated_sections.

## Tests
- extract_code_anchor_claims: parses anchors, position-stripped identity, fence-aware.
- check_code_anchor: resolves -> 0; broken anchor -> exactly one WARNING (not error) with
  the caveat; deterministic sort.
- hash isolation: editing prose under .codas/wiki/code/ leaves inventory byte-identical.
- repo: the committed openworld.md anchors resolve -> check 0; orchestration monkeypatch.
