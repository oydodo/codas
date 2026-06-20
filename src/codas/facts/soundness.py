from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Optional

# B2 — fact soundness qualifier. A deterministic, declarative SOUNDNESS marker for
# the code-fact families (symbols / imports / calls). It overcomes critique defect C
# ("deterministic conflated with correct"): a static call graph is byte-identical AND
# approximate, but the facts themselves carry no marker saying so, so a consumer can
# wrongly read absence-of-edge as proof-of-no-call. Soundness is a property of the
# SENSOR (per family), NOT of each row, so it is declared once here, per family.
#
# Pure stdlib, a frozen constant manifest + a pure ``min`` (meet) algebra: no LLM, no
# nondeterminism (§17). This module lives in the ``codas.facts`` seam but — unlike
# ``context``/``snapshot`` — it imports NO adapter; it is a constant manifest, so ANY
# layer may import it (the same allowed app->facts direction ``impact`` already uses
# for ``CallFacts``).


class SoundnessLevel(IntEnum):
    """The primitive soundness levels, in a TOTAL order by strength (descending).

    ``EXACT`` > ``SCOPED`` > ``APPROXIMATE_INCOMPLETE``. The explicit numeric rank lets
    :func:`meet` be a plain ``min`` (the weakest input wins). ("derived" is NOT a
    primitive level — it is what :func:`meet` produces when it composes a claim from
    several families; document, do not enumerate, it.)

    - ``EXACT``: complete + precise for what it claims.
    - ``SCOPED``: complete WITHIN a declared scope (the bound is stated in ``scope``),
      with nothing missing inside that scope.
    - ``APPROXIMATE_INCOMPLETE``: known to under-approximate (the gaps are named in
      ``under_approximates``).
    """

    EXACT = 2
    SCOPED = 1
    APPROXIMATE_INCOMPLETE = 0


# rank -> lowercase name and name -> rank. Serialization uses the lowercase NAME string
# (e.g. "approximate_incomplete"), never the int rank, so inventory/impact output stays
# stable AND human-legible (the int order is an internal composition detail).
LEVEL_NAMES: dict[int, str] = {
    level.value: level.name.lower() for level in SoundnessLevel
}
LEVEL_RANKS: dict[str, int] = {name: rank for rank, name in LEVEL_NAMES.items()}


def level_name(level: int) -> str:
    """The stable lowercase name for a soundness rank (the serialized form)."""
    return LEVEL_NAMES[int(level)]


def meet(a: int, b: int) -> int:
    """The two-family soundness algebra: the weakest input wins (``min``).

    Pure. Composing facts of differing soundness yields the weakest, because a claim
    built on an approximate input is itself no stronger than that input. Returns a plain
    ``int`` (``min(int(a), int(b))``) so an ``IntEnum`` member never leaks to a consumer.
    """
    return min(int(a), int(b))


def meet_all(levels: Iterable[int]) -> int:
    """``meet`` folded over many levels; ``EXACT`` on an empty input (the lattice identity).

    The first multi-family CLAIM consumer is B4 — ``meet``/``meet_all`` is the family
    algebra that consumer will fold over the soundness of every family a claim rests on.
    PRECONDITION for B4: ``EXACT`` on empty is the algebraic identity (a fold over nothing),
    NOT "a claim resting on no evidence is exact" — a claim with no families is unverifiable
    and B4 must reject it BEFORE calling ``meet_all``, never read EXACT-on-empty as a verdict.
    """
    result = int(SoundnessLevel.EXACT)
    for level in levels:
        result = meet(result, int(level))
    return result


@dataclass(frozen=True)
class FactFamilySoundness:
    """The declared soundness of one code-fact family (a sensor property).

    ``level`` is a :class:`SoundnessLevel` rank (int); ``scope`` states the bound an
    ``SCOPED`` family is complete within; ``under_approximates`` names the gaps an
    ``APPROXIMATE_INCOMPLETE`` family is known to miss.
    """

    family: str
    level: int
    scope: str
    under_approximates: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Sorted-keys dict for inventory/impact; ``level`` is the LOWERCASE name string.

        Serializing the lowercase name (e.g. ``"approximate_incomplete"``), never the
        int rank, keeps the surfaced output stable and human-legible; the gaps are a
        sorted list so the output is byte-identical run-to-run.
        """
        return {
            "family": self.family,
            "level": level_name(self.level),
            "scope": self.scope,
            "under_approximates": sorted(self.under_approximates),
        }


# The frozen manifest: per-family declared soundness for the three code-fact families.
# A STATIC constant — adding it changes the inventory hash exactly once, then two
# consecutive runs stay byte-identical. The under_approximates lists mirror the real
# gaps the extractors document (see codas.adapters.callgraph's "determinism is the
# property; pyan is the anti-pattern" docstring for the calls gaps).
FACT_SOUNDNESS: dict[str, FactFamilySoundness] = {
    "symbols": FactFamilySoundness(
        family="symbols",
        level=int(SoundnessLevel.SCOPED),
        scope="top-level Python definitions (class/function) resolved by stdlib ast",
        under_approximates=(
            "methods",
            "nested definitions",
            "conditionally-defined or dynamically-created symbols",
        ),
    ),
    "imports": FactFamilySoundness(
        family="imports",
        level=int(SoundnessLevel.APPROXIMATE_INCOMPLETE),
        scope="static Python import statements, first-party targets resolved by stdlib ast",
        under_approximates=(
            # NB the extractor uses ast.walk, so conditional + function-local import
            # STATEMENTS ARE reached — claiming otherwise would over-state incompleteness
            # (codex B2 review). The real gaps are dynamic and re-export forms:
            "dynamic imports (importlib / __import__)",
            "re-export resolution (a `from x import y` re-export is the import edge, not a new symbol)",
        ),
    ),
    "calls": FactFamilySoundness(
        family="calls",
        level=int(SoundnessLevel.APPROXIMATE_INCOMPLETE),
        scope="first-party static-resolved call edges in function/method BODIES (stdlib ast, no third-party analyzer)",
        under_approximates=(
            # SCOPE gap (codex B2 BLOCKER): _module_edges only walks function and method
            # bodies, so calls OUTSIDE a body are dropped and were previously undisclosed.
            "calls outside a function/method body (module-level, class-body, decorator, or default-argument expressions)",
            "dynamic dispatch / calls through variables or returns",
            "super() / MRO / cross-class instance dispatch",
            "reflection (getattr / dynamic)",
            "builtins and external (non-first-party) calls",
        ),
    ),
}


def family_soundness(family: str) -> Optional[FactFamilySoundness]:
    """The declared soundness for ``family`` (``symbols``/``imports``/``calls``), or None."""
    return FACT_SOUNDNESS.get(family)
