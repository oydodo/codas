# Design — the open-world invariant (slim B2)

## The invariant (the durable statement)
Static code-fact families (symbols/imports/calls, + pattern-extracted doc/wiki path refs)
are OPEN-world: each emitted fact is SOUND (conservative extractor; emits only resolved,
drops the rest), so a POSITIVE reading is 100% reliable, but ABSENCE is not evidence
(completeness over runtime behavior is undecidable — Rice). Config/declared families
(units/tasks/work_items/documents) are CLOSED-world: read in full, so absence IS evidence.

## Two consumers of the invariant
1. POLICIES never GATE on the absence of an open-world fact — they gate on PRESENCE
   (duplicate_implementation, dependency_direction). There is deliberately no "dead code"
   gate (it would gate `calls` absence and false-positive on dynamic dispatch).
2. A reasoner over these facts (today codas impact; later an LLM/claim verifier) reads
   absence as UNKNOWN, not denial.

## What ships now vs deferred
NOW: the invariant as documentation (codas.facts.openworld module docstring) + OPEN_WORLD_GAPS
(named, ground-truthed gaps) + open_world_gaps() + the codas impact lower-bound caveat.
DEFERRED to the generic LLM/claim-verifier layer: a serialized per-family open/closed MARKER
in inventory (needs a generic consumer + extensible families to earn its place).

## Ground-truthing (the B2 review lesson)
A disclosed gap must be DEMONSTRABLE by running the real extractor, never merely asserted.
tests/test_openworld.py proves: calls drop out-of-body call forms; symbols drop
conditional/dynamic defs; imports does NOT over-claim conditional/local (ast.walk reaches
them). A gap in the list without a proof is decoration.

## Why not keep the graded level
The level had no consumer behavior attached: for a POSITIVE claim every level is fine; for a
NEGATIVE claim every open-world level is "don't trust absence". So the only operational bit
is binary, and within static code facts it is constant (always open) -> a per-family graded
field is information-free. Dropped.
