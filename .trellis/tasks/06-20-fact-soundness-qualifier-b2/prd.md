# B2 — fact soundness qualifier

## Status
PLANNING — first code slice of the patched perception model (see the 06-20
perception-model decision record). Overcomes critique defect C ("deterministic conflated
with correct"): a static call-graph is byte-identical AND approximate, but the facts carry
no marker saying so, so a consumer can wrongly read absence-of-edge as proof-of-no-call.

## Scope
Add a deterministic, declarative SOUNDNESS qualifier to the code-fact families
(symbols / imports / calls) and make the approximation HONEST at the one in-repo consumer
that presents call facts as if complete (`codas impact`). Per-FAMILY (a soundness is a
property of the sensor, not of each row), NOT per-edge.

## Out of scope
- The claim-schema object + MEET-on-claim-verification consumer (that is B4); B2 ships the
  `meet()` algebra + manifest, its multi-family claim consumer comes later.
- Changing any extraction behavior or any gate/policy verdict — purely additive/descriptive.
- Soundness for non-code fact families (doc/wiki/structure) — later.

## Acceptance
- [ ] A `fact_soundness` manifest declares, per family, a level + scope + the named
      under-approximations (e.g. calls misses dynamic dispatch / super/MRO / reflection).
- [ ] The manifest is surfaced in `codas inventory` (deterministic, byte-identical 2x).
- [ ] `codas impact` output (text + --json) carries the calls-family soundness so the
      impact set is presented as a lower bound, not complete.
- [ ] `meet()` composes levels (weakest wins), unit-tested.
- [ ] `codas check .` = 0; full suite green; §17/§11 clean; wiki --verify clean.
