# Slim B2 to the open-world invariant (supersedes the graded soundness qualifier)

## Status
PLANNING — corrects B2 (06-20-fact-soundness-qualifier-b2, commit 82804b6) after a design
discussion concluded its graded soundness LEVEL was over-engineering.

## Why
B2 shipped a graded per-family soundness LEVEL (EXACT/SCOPED/APPROXIMATE + a meet lattice,
serialized into inventory as a fact_soundness block). The level carries NO decision: static
code facts are uniformly OPEN-world (completeness over runtime behavior is undecidable —
Rice), so a graded "how complete" level is information-free; the only operational content is
the binary open/closed distinction ("can a consumer trust this fact's ABSENCE?"). And a
per-family open/closed MARKER serialized into inventory is premature: it only earns its place
once a GENERIC consumer (extensible multi-language fact families + an LLM/claim verifier that
must handle a new family's world without hardcoding) needs it as data. Today's consumers are
specific. So: keep the invariant as documentation + ground-truthed gaps + the one live
consumer (codas impact); defer the data marker. Also: "soundness" was the wrong word (facts
ARE sound; the issue is completeness/open-world) — leaving the name is itself a stale claim.

## Scope
- Replace src/codas/facts/soundness.py with codas.facts.openworld: the documented OPEN-WORLD
  invariant + OPEN_WORLD_GAPS (named gaps per static code family) + open_world_gaps(family).
  Remove SoundnessLevel / meet / meet_all / FactFamilySoundness / FACT_SOUNDNESS.
- Remove the inventory fact_soundness block.
- codas impact: result carries `open_world {is_lower_bound, misses}`; caveat reworded.
- fact_coupling comment: reference the open-world invariant.
- CONTEXT.md perception panorama: open/closed-world, not graded soundness.
- Keep the GROUND-TRUTH gap tests (run the real extractor, prove each gap is real).

## Acceptance
- [ ] No graded level / meet / serialized soundness block remains; openworld module + gaps +
      the impact caveat (matched + miss) remain; gaps ground-truthed by tests.
- [ ] codas check . = 0; inventory byte-identical 2x; full suite green; wiki --verify clean.
