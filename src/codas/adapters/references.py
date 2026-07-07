from __future__ import annotations

from dataclasses import dataclass

from codas.adapters.python import ImportFact, ImportFacts


@dataclass(frozen=True)
class DefinitionRecord:
    name: str
    qualified_name: str
    module: str
    path: str
    kind: str
    line: int


@dataclass(frozen=True)
class ReferenceCandidate:
    name: str
    qualified_name: str | None
    module: str
    path: str
    line: int
    syntax_kind: str


def resolve_reference_edges(
    definitions: tuple[DefinitionRecord, ...],
    references: tuple[ReferenceCandidate, ...],
) -> ImportFacts:
    """Resolve explicit code references into first-party dependency edges.

    Adapters own grammar-specific extraction. This helper owns the shared conservative
    rule: exact qualified match first, then simple-name fallback, and only when the
    selected key has exactly one first-party definition. Ambiguous or unresolved names
    emit no fact; absence stays open-world.
    """
    by_qualified: dict[str, list[DefinitionRecord]] = {}
    by_name: dict[str, list[DefinitionRecord]] = {}
    for definition in definitions:
        if definition.qualified_name:
            by_qualified.setdefault(definition.qualified_name, []).append(definition)
        by_name.setdefault(definition.name, []).append(definition)

    first_line: dict[tuple[str, str, str], int] = {}
    for reference in references:
        resolved = _resolve_reference_candidate(reference, by_qualified, by_name)
        if resolved is None:
            continue
        target, definition = resolved
        if definition.path == reference.path:
            continue
        key = (reference.path, target, definition.path)
        if key not in first_line or reference.line < first_line[key]:
            first_line[key] = reference.line

    imports = tuple(
        sorted(
            (
                ImportFact(module=module, target=target, target_path=target_path, line=line)
                for (module, target, target_path), line in first_line.items()
            ),
            key=lambda fact: (fact.module, fact.line, fact.target, fact.target_path or ""),
        )
    )
    return ImportFacts(imports=imports, skipped=())


def _resolve_reference_candidate(
    reference: ReferenceCandidate,
    by_qualified: dict[str, list[DefinitionRecord]],
    by_name: dict[str, list[DefinitionRecord]],
) -> tuple[str, DefinitionRecord] | None:
    if reference.qualified_name:
        qualified = by_qualified.get(reference.qualified_name, ())
        if len(qualified) == 1:
            return reference.qualified_name, qualified[0]
        if len(qualified) > 1:
            return None

    simple = by_name.get(reference.name, ())
    if len(simple) == 1:
        return reference.name, simple[0]
    return None
