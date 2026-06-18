from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codas.adapters.markdown import DocClaim, extract_doc_claims
from codas.adapters.python import SymbolFact, SymbolFacts, extract_symbol_facts
from codas.config.loader import CodasConfig
from codas.structure.index import discover_files, workspace_roots

# The facts seam surfaces the normalized fact vocabulary so policies can name the
# fact types (DocClaim/SymbolFact) without importing an ecosystem adapter. The
# dataclasses physically live in codas.adapters today; relocating them into a
# neutral codas.facts types module is a later cleanup (P3-follow-up).
__all__ = [
    "ScanContext",
    "build_scan_context",
    "DocClaim",
    "SymbolFact",
    "SymbolFacts",
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

    def symbols(self) -> SymbolFacts:
        """Python top-level symbol facts for the scanned tree (cached, adapter-sorted)."""
        if "symbols" not in self._cache:
            self._cache["symbols"] = extract_symbol_facts(self.repo, self.files)
        return self._cache["symbols"]


def build_scan_context(repo: Path, config: CodasConfig) -> ScanContext:
    """Build the per-run `ScanContext`: resolve roots and scan the tree once."""
    roots = workspace_roots(config.raw)
    files = tuple(discover_files(repo, roots))
    return ScanContext(repo=repo, config=config, roots=roots, files=files)
