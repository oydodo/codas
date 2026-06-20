from __future__ import annotations

# The OPEN-WORLD invariant for code-extracted facts.
#
# A CORE INVARIANT (no code enforces it as a gate; it constrains how facts may be
# consumed): facts produced by STATIC code analysis are OPEN-WORLD — they are a sound
# LOWER BOUND, never a complete set. The code-fact families symbols / imports / calls are
# open-world; the pattern-extracted doc/wiki path references are ALSO open-world in
# principle (regex misses path refs in bare prose / unusual forms), but they have no
# consumer of their gaps today, so — per the "don't pre-build for an absent consumer"
# rationale below — they are NOT enumerated in OPEN_WORLD_GAPS yet. Each emitted fact is
# true (the extractor is conservative:
# it emits only what it resolves and drops the rest), so a POSITIVE reading is 100%
# reliable ("A calls B" is real). But ABSENCE is NOT evidence: "no edge A->B" does not
# mean A never calls B — it may be a dynamic/reflective form the static extractor cannot
# decide (Rice's theorem: completeness over runtime behavior is undecidable). By contrast
# the CONFIG/DECLARED fact families (structure units, tasks, work-items, documents) are
# CLOSED-WORLD: they are read in full from a bounded artifact, so their absence IS
# evidence ("structure.yml declares no unit X" => X is genuinely undeclared).
#
# CONSEQUENCES (the invariant's two consumers):
#   1. POLICIES must not GATE on the absence of an open-world fact. The deterministic
#      policies gate on PRESENCE (duplicate_implementation: two defs found; dependency_
#      direction: an edge found) — there is deliberately no "dead code" gate, because it
#      would gate on the absence of `calls` edges and false-positive on dynamic dispatch.
#   2. A consumer reasoning over these facts (today: `codas impact`; later: an LLM/claim
#      verifier judging semantic legality) must read absence as UNKNOWN, not as denial.
#
# This module deliberately does NOT serialize a per-family open/closed MARKER into the
# inventory. That marker only earns its place once there is a GENERIC consumer (an
# extensible multi-language fact set + an LLM claim-verifier that must handle a new
# family's world without hardcoding it) — deferred to that layer. For now the invariant
# is documentation + the named open-world gaps below (each proven real by a test in
# tests/test_openworld.py, so the disclosure is ground-truthed, never merely asserted)
# + the one live consumer, `codas impact`, which renders the lower-bound caveat.
#
# History: this replaces the B2 graded "soundness qualifier" (EXACT/SCOPED/APPROXIMATE +
# a meet lattice, serialized into inventory). That gradation was information-free — static
# code facts are uniformly open-world (completeness is undecidable, never a confirmable
# level), so a per-family graded level carried no decision. The operational content is the
# single open/closed distinction, captured here as the invariant + the gaps.


# The named gaps each OPEN-WORLD code-fact family is known to miss. Documentation for a
# consumer + the surface a ground-truth test pins (a gap claimed here must be DEMONSTRABLE
# by running the real extractor). Only the code-fact families that HAVE a consumer today
# (impact / fact_coupling) are listed. A family's ABSENCE from this map does NOT assert it
# is closed-world — it may be an open-world family without a current gap consumer (doc/wiki
# path refs). The genuinely CLOSED-world families (absence IS evidence) are the config/
# declared ones named in the module docstring (units / tasks / work-items / documents); do
# not infer closed-world from `open_world_gaps(...) == ()`.
OPEN_WORLD_GAPS: dict[str, tuple[str, ...]] = {
    "symbols": (
        # bounded/decidable gaps (a better extractor could close these):
        "conditionally-defined top-level symbols (def/class inside an if/try body)",
        # unbounded/undecidable gap (Rice -- never closeable):
        "dynamically-created symbols (globals()[...] / type() / exec)",
    ),
    "imports": (
        "dynamic imports (importlib / __import__)",
        "re-export resolution (a `from x import y` re-export is the edge, not a new symbol)",
    ),
    "calls": (
        # SCOPE gap: the extractor only walks function/method BODIES.
        "calls outside a function/method body (module-level, class-body, decorator, or default-argument expressions)",
        "dynamic dispatch / calls through variables or returns",
        "super() / MRO / cross-class instance dispatch",
        "reflection (getattr / dynamic)",
        "builtins and external (non-first-party) calls",
    ),
}


def open_world_gaps(family: str) -> tuple[str, ...]:
    """The named open-world gaps for ``family`` (a listed code-fact family), or ``()``.

    A NON-EMPTY result means the family is open-world: a consumer must read absence as a
    lower bound, not as denial, and the items name the specific forms the extractor misses.

    ``()`` is NOT an assertion of closed-world — it only means ``family`` is not in the
    consumer-scoped gap list (a closed-world config family, an open-world family without a
    current gap consumer, or an unknown name). Whether a family is closed-world (absence is
    trustworthy) is stated in the module docstring, not derived from this ``()`` — a future
    generic verifier must consult that, never read ``()`` here as "closed-world".
    """
    return OPEN_WORLD_GAPS.get(family, ())
