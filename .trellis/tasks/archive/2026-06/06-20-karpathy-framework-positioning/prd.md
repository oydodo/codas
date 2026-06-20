# Record the Karpathy-LLM-wiki-framework positioning + 3-way comparison

## Status
PLANNING → docs-only. No code, no gate semantics (∴ no codex DESIGN review required).
Content was adversarially hardened by a 5-agent research+critique workflow (Karpathy /
FSoft CodeWiki / Codas maps → synthesis → skeptic critique); this task only records the
converged conclusion in an authoritative doc.

## Why
A conceptual thread this session produced the cleanest external POSITIONING Codas has had:
framed in Andrej Karpathy's "LLM-wiki / docs-for-agents" model, Codas's route is —
**(1) the wiki layer is PLUGGABLE (CodeWiki / host-agent / none); (2) schema, (3) authoring,
(4) maintenance are where Codas wins — by turning each from a CONVENTION (human goodwill)
into an ENFORCED ARTIFACT (a gate that fails if you don't).** This belongs in the
authoritative context doc next to the Perception Model, so the positioning survives context
resets and frames W3 scope.

## Scope
- Append a new `## Positioning` section to CONTEXT.md (authoritative, governed by
  documents.yml). Contains: (a) the Karpathy 4-piece framing; (b) a 3-way comparison matrix
  (Karpathy LLM-wiki / FSoft CodeWiki / Codas) over structure / philosophy / determinism /
  verification / scope; (c) the layer-by-layer route (1 pluggable, 2-3-4 enforced); (d) the
  HONEST caveats from the critic: shipped-vs-planned, wiki = explicit non-goal, W3 only does
  the layer-1 SEAM (feed + calibrate, never author), the **trust-tier TAGS must be assigned
  DETERMINISTICALLY** (else LLM-checks-LLM re-enters at the tagging boundary), the layer-3
  authoring tax, the layer-4 blind spot (doc→code drift uncaught), and that CodeWiki is an
  instance of the wiki-generator CATEGORY, not an implementation of Karpathy's specific model.

## Doc-claim safety (CONTEXT.md is scanned by the markdown adapter)
A backtick token becomes a `code` doc-claim ONLY if it has BOTH a slash AND a known extension
(markdown.py `_normalize`), so it must resolve to a real file or `stale_claim` fires. Keep
backtick `path/with.ext` refs to real files only; use plain `name` (no slash/ext) for
everything else. No markdown `[text](path)` links to non-existent files.

## Acceptance
- [ ] New `## Positioning` section in CONTEXT.md with the comparison matrix + the 1-pluggable
      / 2-3-4-enforced route + the honest caveats.
- [ ] `codas check .` == 0 (no new unresolved doc-claims).
- [ ] inventory byte-identical across two runs; full test suite green; wiki --verify clean.
- [ ] No code / no policy / no gate change.
