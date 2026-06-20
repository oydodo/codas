from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codas.adapters.callgraph import CallFacts, extract_call_facts_from_parsed
from codas.adapters.git import list_python_paths_at_head, read_blob_at_head
from codas.adapters.python import (
    ImportFacts,
    SymbolFacts,
    extract_import_facts_from_parsed,
    extract_symbol_facts_from_parsed,
)
from codas.adapters.python_parse import ParsedModules, parse_sources
from codas.structure.index import filter_to_roots


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


def head_snapshot(repo: Path, roots: tuple[str, ...]) -> FactSnapshot | None:
    """The code-fact snapshot of the committed tree at ``HEAD``.

    Lists ``.py`` blobs at ``HEAD``, filters to the configured workspace ``roots``
    with the SAME discipline as the working-tree scan (:func:`filter_to_roots`), reads
    each blob, parses, and projects. Returns ``None`` when ``HEAD`` does not resolve
    (no commits / not a repo) OR when any blob read fails — never a partial snapshot,
    because a missing file would otherwise read as its facts being "removed" (false
    drift). The caller treats ``None`` as "no baseline".
    """
    listed = list_python_paths_at_head(repo)
    if listed is None:
        return None
    keep = set(filter_to_roots([path for path, _ in listed], roots))
    sources: dict[str, str] = {}
    for path, blob_sha in listed:  # already sorted by path
        if path not in keep:
            continue
        blob = read_blob_at_head(repo, blob_sha)
        if blob is None:
            return None  # no partial snapshot
        sources[path] = blob
    return snapshot_from_parsed(parse_sources(sources))
