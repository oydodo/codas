from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codas.adapters.git import extract_changed_paths
from codas.adapters.html import extract_html_claims, governed_html_files
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
from codas.adapters.semantic import (
    SemanticClaims,
    StructuralClaim,
    extract_semantic_claims,
)
from codas.config.loader import CodasConfig
from codas.facts.delta import FactDelta, diff_snapshots
from codas.facts.snapshot import FactSnapshot
from codas.facts.snapshot import head_snapshot as compute_head_snapshot
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
    "StructuralClaim",
    "SemanticClaims",
    "CallFact",
    "CallFacts",
    "FactSnapshot",
    "FactDelta",
]

# An empty baseline snapshot — the delta base when HEAD has no commits (every
# working-tree fact then reads as "added"; the policy layer decides if a no-baseline
# repo is exempt).
_EMPTY_SNAPSHOT = FactSnapshot(
    symbols=SymbolFacts((), ()),
    imports=ImportFacts((), ()),
    calls=CallFacts((), ()),
)


@dataclass(frozen=True)
class ScanContext:
    """The fact-provider seam: one file scan + adapter extraction per run.

    `ScanContext` is the normalization layer between ecosystem adapters and the
    policy engine (plan §11 Adapter Boundary: "Core may only receive normalized
    facts and claims"). It is where adapter output crosses into normalized facts —
    `codas.facts` is the seam, so its modules (`context`, `snapshot`) are the place
    outside `codas.adapters` permitted to import an adapter. Policies receive a
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

    def html_claims(self) -> tuple[DocClaim, ...]:
        """Path/link claims from config-declared authoritative+supporting ``.html`` (cached).

        Parallels ``doc_claims()`` but config-SCOPED — arbitrary ``.html`` is not governed
        (only constraint sources, matched by ``fnmatch`` so a glob source is honored).
        Consumed by ``stale_html_claim``; a disjoint fact stream from ``doc_claims()``
        (markdown), so the two ``stale_*`` policies never double-report. These ARE facts,
        so they enter ``inventory`` (the ``html_claims`` block).
        """
        if "html_claims" not in self._cache:
            patterns = self.config.authoritative_sources + self.config.supporting_sources
            scoped = governed_html_files(self.files, patterns)
            self._cache["html_claims"] = tuple(extract_html_claims(self.repo, scoped))
        return self._cache["html_claims"]

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
            self._cache["calls"] = extract_call_facts_from_parsed(self._parsed())
        return self._cache["calls"]

    def changed_paths(self) -> tuple[str, ...]:
        """Working-tree paths differing from HEAD (cached; git diff substrate).

        Policy-time fact consumed by ``fact_coupling``; deliberately *not* serialized
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

    def code_anchor_claims(self) -> SemanticClaims:
        """Structural claims (defines/calls/contains) parsed from the COMMITTED code-wiki
        pages under ``.codas/wiki/code/`` (cached).

        W5: the code-wiki and the former committed semantic-wiki are UNIFIED on the full
        ``defines/calls/contains`` grammar (``extract_semantic_claims``); the old
        ``anchor_symbol`` keyword is the ``defines``-to-a-top-level-symbol case. Read from the
        DISCOVERED file set (tracked + untracked-non-ignored), so a still-uncommitted draft is
        also verified — a helpful warning while authoring.

        A policy-time fact consumed by ``code_anchor``; deliberately NOT serialized into
        ``inventory`` (the ``.codas/wiki/code/`` prose is excluded from the doc/wiki claim
        streams via markdown ``SKIP_PREFIXES`` + ``extract_wiki_claims``, and these claims are
        position-stripped — so the code-wiki never perturbs the byte-identical inventory hash).
        Distinct from the gitignored OFFLINE W3 cache ``semantic_corpus_claims()`` reads.
        """
        if "code_anchor_claims" not in self._cache:
            wiki_root = (self.config.raw.get("wiki") or {}).get("path", ".codas/wiki")
            root = wiki_root.rstrip("/") + "/code"
            self._cache["code_anchor_claims"] = extract_semantic_claims(
                self.repo, root, self.files
            )
        return self._cache["code_anchor_claims"]

    def semantic_corpus_claims(self) -> SemanticClaims:
        """Structural claims parsed from the OFFLINE semantic corpus (cached).

        Read directly from `.codas/cache/semantic/` — gitignored, so NOT in `self.files`
        and never discovered into the inventory (it cannot perturb the byte-identical
        hash). Consumed ONLY by the W3 calibrator (`codas wiki --calibrate`), never by a
        check-time policy — so the offline corpus stays off the always-on `codas check`
        path. Requires a git repo for the gitignore exclusion to hold (already an implied
        operating assumption for the git-based facts). NB the sibling `code_anchor_claims()`
        reads the COMMITTED `.codas/wiki/code/` (tracked) with the SAME grammar and IS consumed
        by a check policy — do not conflate the offline cache with the committed code-wiki.
        """
        if "semantic_corpus_claims" not in self._cache:
            self._cache["semantic_corpus_claims"] = extract_semantic_claims(self.repo)
        return self._cache["semantic_corpus_claims"]


    def working_snapshot(self) -> FactSnapshot:
        """The code-fact snapshot of the scanned working tree (cached).

        Reuses the already-memoized ``symbols``/``imports``/``calls`` — one
        computation, identical to the inventory's projection of the same facts.
        """
        if "working_snapshot" not in self._cache:
            self._cache["working_snapshot"] = FactSnapshot(
                symbols=self.symbols(), imports=self.imports(), calls=self.calls()
            )
        return self._cache["working_snapshot"]

    def head_snapshot(self) -> FactSnapshot | None:
        """The code-fact snapshot at ``HEAD`` (cached); ``None`` if HEAD is unavailable.

        A policy-time fact (reflects the committed ref, not serialized into the
        byte-identical ``inventory``). ``None`` when there is no baseline (no commits
        / not a repo / a blob read failed — never a partial snapshot).
        """
        if "head_snapshot" not in self._cache:
            self._cache["head_snapshot"] = compute_head_snapshot(self.repo, self.roots)
        return self._cache["head_snapshot"]

    def fact_delta(self) -> FactDelta:
        """Code facts added/removed between ``HEAD`` and the working tree (cached).

        The deterministic substrate for the spec-drift v2 fact-level couplings: a
        coupling fires when its watched fact-delta is nonempty. On a clean tree
        (HEAD == working, nothing staged) the delta is empty. When HEAD has no
        baseline every working-tree fact reads as "added".
        """
        if "fact_delta" not in self._cache:
            head = self.head_snapshot()
            base = head if head is not None else _EMPTY_SNAPSHOT
            self._cache["fact_delta"] = diff_snapshots(base, self.working_snapshot())
        return self._cache["fact_delta"]


def build_scan_context(repo: Path, config: CodasConfig) -> ScanContext:
    """Build the per-run `ScanContext`: resolve roots and scan the tree once."""
    roots = workspace_roots(config.raw)
    files = tuple(discover_files(repo, roots))
    return ScanContext(repo=repo, config=config, roots=roots, files=files)
