# Atlas code-wiki — committed wiki + all-open code-anchor verifier (W1)

## Status
PLANNING. First buildable slice of the code-wiki, after an adversarial design review
(workflow w8v8wge2q, verdict SOUND-BUT-NEEDS-PATCHES) + the user's asymmetry refinement.

## The design (patched)
A COMMITTED Atlas code-wiki: one page per module/concept = advisory PROSE (the semantic
"flesh" facts lack; doubles as the agent's code-picture for preflight) + a structured
atlas:claims block carrying CODE-ANCHORS. Codas verifies ONLY the code-anchors, never the
prose. The user's asymmetry: the doc->code direction (a user-driven doc edit -> the agent
follows in Trellis) is low-risk and NOT gated; the code->doc direction (the agent edits
code during impl and forgets the doc) is the real drift -> Codas catches it by checking the
wiki's code-anchors still resolve against current facts.

## Load-bearing decisions (from the review + the dialogue)
- VERIFY CODE-ANCHORS, NOT PROSE. The prose is advisory/supporting-tier; Codas does not
  verify its meaning (that is the later LLM-judge's job).
- ALL-OPEN (deferred world-split): a non-resolving anchor -> WARNING/residue, NEVER a hard
  error. Strict application of the open-world invariant (never gate on absence). Zero
  false-positives on super()/MRO/conditional/dynamic forms. Harder closed-world gating
  (a genuinely-deleted top-level def -> error) is a LATER optimization.
- PROSE STAYS OUT OF THE BYTE-IDENTICAL HASH. The code-anchor claims are a POLICY-TIME
  fact (like generated_claims / changed_paths) read via ScanContext and NOT serialized into
  inventory -> no hash concern by construction. The LLM-wiki dir is excluded from the
  doc_claims + wiki_claims ingestion so its prose path-refs (with line numbers) never enter
  the inventory hash. The wiki is NOT routed through the byte-rerender `wiki --verify` path.
- NOT the deterministic generated/ machinery: this is a NEW reader + verifier (the
  generated_wiki_drift grammar only knows unit/roadmap; a new kind would be silently
  dropped). Net-new, honestly.

## Scope (first slice)
- ONE new anchor kind: `anchor_symbol: <concept> -> <path>:<name>` inside the atlas:claims
  block. (import/call anchors = later.)
- A reader `extract_code_anchor_claims` (parallel to extract_generated_claims), POSITION-
  STRIPPED identity, scoped to the LLM-wiki dir.
- `ScanContext.code_anchor_claims()` (policy-time seam, not in inventory).
- A verifier policy `check_code_anchor` (warning): each anchor resolves against ctx.symbols()
  -> non-resolve = warning carrying the open_world lower-bound caveat.
- Exclude the LLM-wiki dir from doc_claims + wiki_claims ingestion (prose out of the hash).
- ONE hand-authored code-wiki page for a real Codas module (the manual "host-agent
  generation"), anchors resolving -> check stays clean.

## Out of scope (later)
- import/call anchors; the closed-world hard-gate optimization; the LLM JUDGE layer
  (on-demand semantic suggestions); preflight integration (wiki as code-picture); OSS
  generator injection.

## Acceptance
- [ ] A committed code-wiki page's anchors resolve -> check 0 (no warning).
- [ ] A fixture page with a broken anchor -> `check` emits a WARNING (not an error),
      carrying the open-world caveat; deterministic.
- [ ] Prose edits to the wiki do NOT change the inventory hash (prose out of the hash);
      byte-identical 2x.
- [ ] §11/§17 clean; full suite green; `wiki --verify` unaffected.
