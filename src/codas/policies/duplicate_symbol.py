from __future__ import annotations

from collections import defaultdict

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext, SymbolFact

SCOPE_PREFIX = "src/"


def check_duplicate_symbol(ctx: ScanContext) -> list[Finding]:
    """Flag public top-level symbol names defined in two or more src modules.

    Deterministic, language-adapter-level first cut of duplicate detection (plan
    §10 ``duplicate_symbol``: "Language adapters emit repeated type/function
    names"). Scoped to public symbols (no leading underscore) under ``src/``:
    leading-underscore module helpers are local encapsulation, not duplicate
    implementations, and ``tests/`` / vendored ``.trellis`` modules legitimately
    repeat names. Severity is warning — a name collision is a candidate signal,
    not proof; the error-severity, claim-aware ``duplicate_implementation`` (and
    the semantic ``duplicate_concept``) are later. No LLM (plan §17).

    Consumes normalized symbol facts from the `ScanContext` (plan §11 Adapter
    Boundary) — it does not import the Python adapter itself.
    """
    facts = ctx.symbols()

    by_name: dict[str, list[SymbolFact]] = defaultdict(list)
    for definition in facts.definitions:
        if definition.module.startswith(SCOPE_PREFIX) and not definition.name.startswith("_"):
            by_name[definition.name].append(definition)

    findings: list[Finding] = []
    for name in sorted(by_name):
        occurrences = by_name[name]
        modules = sorted({occ.module for occ in occurrences})
        if len(modules) < 2:
            continue
        evidence = [
            Evidence(path=occ.module, line=occ.line, detail=occ.kind)
            for occ in sorted(occurrences, key=lambda occ: (occ.module, occ.line))
        ]
        findings.append(
            Finding(
                severity="warning",
                check_id="duplicate-symbol",
                message=(
                    f"Public symbol '{name}' is defined in {len(modules)} modules: "
                    f"{', '.join(modules)}"
                ),
                evidence=evidence,
                recommendation=(
                    "Consolidate into one definition, declare a "
                    "canonical/variant/migration relationship, or add a waiver."
                ),
                meta={"name": name, "modules": modules},
            )
        )

    findings.sort(key=lambda finding: finding.meta["name"])
    return findings
