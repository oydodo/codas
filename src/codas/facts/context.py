from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codas.adapters.git import extract_changed_paths
from codas.adapters.markdown import DocClaim, extract_doc_claims
from codas.adapters.callgraph import CallFact, CallFacts, extract_call_facts_from_parsed
from codas.adapters.python import (
    ImportFact,
    ImportFacts,
    SymbolFact,
    SymbolFacts,
    extract_import_facts_from_parsed,
    extract_symbol_facts_from_parsed,
)
from codas.adapters.python_parse import ParsedModules, parse_python_modules
from codas.adapters.wiki import (
    GeneratedClaim,
    GeneratedClaims,
    GeneratedPage,
    WikiClaim,
    WikiClaims,
    extract_generated_claims,
    extract_wiki_claims,
)
from codas.config.loader import CodasConfig
from codas.structure.index import discover_files, workspace_roots

# The facts seam surfaces the normalized fact vocabulary so policies can name the
# fact types (DocClaim/SymbolFact/ImportFact) without importing an ecosystem
# adapter. The dataclasses physically live in codas.adapters today; relocating them
# into a neutral codas.facts types module is a later cleanup (P3-follow-up).
__all__ = [
    "ScanContext",
    "build_scan_context",
    "DocClaim",
    "SymbolFact",
    "SymbolFacts",
    "ImportFact",
    "ImportFacts",
    "WikiClaim",
    "WikiClaims",
    "GeneratedClaim",
    "GeneratedPage",
    "GeneratedClaims",
    "CallFact",
    "CallFacts",
]


@dataclass(frozen=True)
class ScanContext:
    """The fact-provider seam: one file scan + adapter extraction per run.

    `ScanContext` is the normalization layer between ecosystem adapters and the
    policy engine (plan §11 Adapter Boundary: "Core may only receive normalized
    facts and claims"). It is the single point where adapter output crosses into
    normalized facts — `codas.facts.context` is therefore the one place outside
    `codas.adapters` that is permitted to import an adapter. Policies receive a
    `ScanContext` and never import an adapter themselves.

    `files` (and `roots`) are resolved once at build time so the working-tree scan
    runs a single time instead of once per file-scanning policy. Per-fact
    accessors memoize their adapter call so repeated reads stay cheap and return
    the identical, adapter-sorted result every time (determinism).
    """

    repo: Path
    config: CodasConfig
    roots: tuple[str, ...]
    files: tuple[str, ...]
    _cache: dict = field(default_factory=dict, init=False, compare=False, repr=False)

    def doc_claims(self) -> tuple[DocClaim, ...]:
        """Markdown doc claims for the scanned tree (cached, adapter-sorted)."""
        if "doc_claims" not in self._cache:
            self._cache["doc_claims"] = tuple(extract_doc_claims(self.repo, self.files))
        return self._cache["doc_claims"]

    def _parsed(self) -> ParsedModules:
        """Single per-run ``ast.parse`` pass over the scanned ``.py`` files (cached).

        The shared substrate for ``symbols``/``imports``/``calls`` — one parse per
        file per run instead of one per accessor (previously 3× parse). The
        ``parse_python_modules`` call is the Slice-2 content-hash cache seam.
        """
        if "parsed" not in self._cache:
            self._cache["parsed"] = parse_python_modules(self.repo, self.files)
        return self._cache["parsed"]

    def symbols(self) -> SymbolFacts:
        """Python top-level symbol facts for the scanned tree (cached, adapter-sorted)."""
        if "symbols" not in self._cache:
            self._cache["symbols"] = extract_symbol_facts_from_parsed(self._parsed())
        return self._cache["symbols"]

    def imports(self) -> ImportFacts:
        """Python import (reference) facts for the scanned tree (cached, adapter-sorted)."""
        if "imports" not in self._cache:
            self._cache["imports"] = extract_import_facts_from_parsed(self._parsed())
        return self._cache["imports"]

    def wiki_claims(self) -> WikiClaims:
        """Atlas Wiki structural claims for the scanned tree (cached, adapter-sorted)."""
        if "wiki_claims" not in self._cache:
            wiki_root = (self.config.raw.get("wiki") or {}).get("path", ".codas/wiki")
            self._cache["wiki_claims"] = extract_wiki_claims(
                self.repo, self.files, wiki_root
            )
        return self._cache["wiki_claims"]

    def calls(self) -> CallFacts:
        """Deterministic first-party Python call-graph facts (cached, stdlib ast)."""
        if "calls" not in self._cache:
            self._cache["calls"] = extract_call_facts_from_parsed(self.repo, self._parsed())
        return self._cache["calls"]

    def changed_paths(self) -> tuple[str, ...]:
        """Working-tree paths differing from HEAD (cached; git diff substrate).

        Policy-time fact consumed by ``spec_drift``; deliberately *not* serialized
        into ``inventory`` — it reflects dirty working-tree state and would break the
        byte-identical inventory invariant.
        """
        if "changed_paths" not in self._cache:
            self._cache["changed_paths"] = extract_changed_paths(self.repo)
        return self._cache["changed_paths"]

    def generated_claims(self) -> GeneratedClaims:
        """atlas:claims parsed from committed generated wiki pages (cached).

        A policy-time fact consumed by ``generated_wiki_drift``; deliberately not
        serialized into ``inventory`` (the generated pages are excluded from the
        source_inventory_hash, and their claims never re-enter the hashed inventory).
        """
        if "generated_claims" not in self._cache:
            wiki_root = (self.config.raw.get("wiki") or {}).get("path", ".codas/wiki")
            root = wiki_root.rstrip("/") + "/generated"
            self._cache["generated_claims"] = extract_generated_claims(
                self.repo, self.files, root
            )
        return self._cache["generated_claims"]


def build_scan_context(repo: Path, config: CodasConfig) -> ScanContext:
    """Build the per-run `ScanContext`: resolve roots and scan the tree once."""
    roots = workspace_roots(config.raw)
    files = tuple(discover_files(repo, roots))
    return ScanContext(repo=repo, config=config, roots=roots, files=files)
