from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codas.adapters.callgraph import CallFacts, extract_call_facts_from_parsed
from codas.adapters.git import list_paths_at_head, read_blob_at_head
from codas.adapters.python import (
    ImportFacts,
    SymbolFacts,
    extract_import_facts_from_parsed,
    extract_symbol_facts_from_parsed,
)
from codas.adapters.python_parse import ParsedModules, parse_sources
from codas.facts.languages import (
    LANGUAGE_EXTENSIONS,
    extract_language_imports_from_sources,
    extract_language_symbols_from_sources,
)
from codas.structure.index import DERIVED_OUTPUT_DEFAULT, filter_to_roots

SOURCE_EXTENSIONS = (".py",) + LANGUAGE_EXTENSIONS


@dataclass(frozen=True)
class FactSnapshot:
    """The three code-fact streams (symbols, imports, calls) at one point in time.

    A snapshot is a pure function of (file-set, content): every extractor it runs
    derives package membership from the file SET, never the live filesystem, so the
    SAME builder works for the working tree and for a git ref (``HEAD``). Snapshots
    are policy-time facts — like ``changed_paths`` they reflect mutable/ref state and
    are never serialized into the byte-identical ``inventory``.
    """

    symbols: SymbolFacts
    imports: ImportFacts
    calls: CallFacts


def snapshot_from_parsed(parsed: ParsedModules) -> FactSnapshot:
    """Project a :class:`FactSnapshot` from an already-parsed module set."""
    return FactSnapshot(
        symbols=extract_symbol_facts_from_parsed(parsed),
        imports=extract_import_facts_from_parsed(parsed),
        calls=extract_call_facts_from_parsed(parsed),
    )


def merge_symbol_facts(primary: SymbolFacts, extra: SymbolFacts) -> SymbolFacts:
    """Merge symbol streams, preserving object identity when ``extra`` is empty."""
    if not extra.definitions and not extra.skipped:
        return primary
    definitions = tuple(
        sorted(
            (*primary.definitions, *extra.definitions),
            key=lambda fact: (fact.module, fact.line, fact.name, fact.kind),
        )
    )
    skipped = tuple(sorted((*primary.skipped, *extra.skipped)))
    return SymbolFacts(definitions=definitions, skipped=skipped)


def merge_import_facts(primary: ImportFacts, extra: ImportFacts) -> ImportFacts:
    """Merge import streams, preserving object identity when ``extra`` is empty."""
    if not extra.imports and not extra.skipped:
        return primary
    imports = tuple(
        sorted(
            (*primary.imports, *extra.imports),
            key=lambda fact: (fact.module, fact.line, fact.target),
        )
    )
    skipped = tuple(sorted((*primary.skipped, *extra.skipped)))
    return ImportFacts(imports=imports, skipped=skipped)


def merge_call_facts(primary: CallFacts, extra: CallFacts) -> CallFacts:
    """Merge call streams, preserving object identity when ``extra`` is empty."""
    if not extra.edges and not extra.skipped:
        return primary
    edges = tuple(
        sorted(
            (*primary.edges, *extra.edges),
            key=lambda fact: (
                fact.caller_path,
                fact.caller_class,
                fact.caller_symbol,
                fact.callee_path,
                fact.callee_class,
                fact.callee_symbol,
            ),
        )
    )
    skipped = tuple(sorted((*primary.skipped, *extra.skipped)))
    return CallFacts(edges=edges, skipped=skipped)


def merge_fact_snapshots(primary: FactSnapshot, extra: FactSnapshot) -> FactSnapshot:
    """Merge two fact snapshots, preserving object identity when ``extra`` is empty."""
    symbols = merge_symbol_facts(primary.symbols, extra.symbols)
    imports = merge_import_facts(primary.imports, extra.imports)
    calls = merge_call_facts(primary.calls, extra.calls)
    if (
        symbols is primary.symbols
        and imports is primary.imports
        and calls is primary.calls
    ):
        return primary
    return FactSnapshot(symbols=symbols, imports=imports, calls=calls)


def head_snapshot(
    repo: Path,
    roots: tuple[str, ...],
    derived_prefixes: tuple[str, ...] = DERIVED_OUTPUT_DEFAULT,
) -> FactSnapshot | None:
    """The code-fact snapshot of the committed tree at ``HEAD``.

    Lists registered source blobs at ``HEAD``, filters to the configured workspace ``roots`` and the
    reserved ``derived_prefixes`` with the SAME discipline as the working-tree scan
    (:func:`filter_to_roots`), reads each blob, parses, and projects. Returns ``None`` when
    ``HEAD`` does not resolve (no commits / not a repo) OR when any blob read fails — never a
    partial snapshot, because a missing file would otherwise read as its facts being
    "removed" (false drift). The caller treats ``None`` as "no baseline".
    """
    listed = list_paths_at_head(repo, SOURCE_EXTENSIONS)
    if listed is None:
        return None
    keep = set(filter_to_roots([path for path, _ in listed], roots, derived_prefixes))
    sources: dict[str, str] = {}
    for path, blob_sha in listed:  # already sorted by path
        if path not in keep:
            continue
        blob = read_blob_at_head(repo, blob_sha)
        if blob is None:
            return None  # no partial snapshot
        sources[path] = blob
    python_sources = {path: source for path, source in sources.items() if path.endswith(".py")}
    base = snapshot_from_parsed(parse_sources(python_sources))
    language = FactSnapshot(
        symbols=extract_language_symbols_from_sources(sources),
        imports=extract_language_imports_from_sources(sources),
        calls=CallFacts(edges=(), skipped=()),
    )
    return merge_fact_snapshots(base, language)
