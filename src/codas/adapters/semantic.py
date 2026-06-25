from __future__ import annotations

import posixpath
from html.parser import HTMLParser
from dataclasses import dataclass
from pathlib import Path

from codas.config.anchors import live_doc_anchor_files, unsupported_live_doc_patterns

# The W3 OFFLINE semantic corpus: host-agent-generated prose pages under
# `.codas/cache/semantic/` (gitignored, regenerable, LOCAL — NOT discovered into the
# inventory, so it never perturbs the byte-identical hash). Each page MAY carry a fenced
# ```atlas:claims block of STRUCTURAL claims the deterministic calibrator (app/calibrate.py)
# tiers against facts. This adapter only PARSES claims (§17 — it makes no world/tier
# judgment, runs no model). Read DIRECTLY from disk: the corpus is gitignored, so it is NOT
# in ScanContext.files — the directory is globbed from the repo root instead.

CORPUS_ROOT_DEFAULT = ".codas/cache/semantic"

# The same parser also reads the COMMITTED code-wiki (`.codas/wiki/code/**`, W5-unified onto
# this grammar) — passed the DISCOVERED file set via ScanContext.code_anchor_claims, distinct
# from this gitignored offline cache. One grammar, two corpora (offline cache + committed
# code-wiki).
#
# Grammar (one claim per line, inside a ```atlas:claims fence):
#   defines:  <concept> -> <node-id>          (concept = UNVERIFIED prose; never confirmed)
#   calls:    <node-id> -> <node-id>
#   contains: <node-id>
# node-id = the Block A address "<path>::<class-or-empty>::<symbol>" (count("::")==2) for a
# callable, or a bare repo-rel path (count("::")==0) for a module/package node.
_KINDS = ("defines", "calls", "contains")


@dataclass(frozen=True)
class StructuralClaim:
    """One structural claim from a semantic corpus page. ``kind`` ∈ defines|calls|contains.
    ``subject`` is a node-id; ``object`` is the second node-id for a two-place claim
    (calls / defines target) or ``""``. ``concept`` is UNVERIFIED prose (defines only) —
    NEVER confirmed by a structural match. ``line`` is human evidence only, not identity."""

    source: str
    line: int
    kind: str
    subject: str
    object: str
    concept: str


@dataclass(frozen=True)
class MalformedClaim:
    source: str
    line: int
    detail: str


@dataclass(frozen=True)
class SemanticClaims:
    claims: tuple[StructuralClaim, ...]
    skipped: tuple[str, ...]
    malformed: tuple[MalformedClaim, ...] = ()


def extract_semantic_claims(
    repo: Path,
    corpus_root: str = CORPUS_ROOT_DEFAULT,
    files: tuple[str, ...] | None = None,
) -> SemanticClaims:
    """Parse structural claims from the fenced ``atlas:claims`` block of each ``.md`` page
    under ``corpus_root``. Robust like the W1 anchor reader — a malformed line is skipped,
    never a crash. Deterministic: pages sorted by source, claims in file order. utf-8 pinned.

    ``files=None`` → rglob the directory directly off disk (the gitignored OFFLINE cache, which
    is not in ``ScanContext.files``). ``files`` given → use that TRACKED file list filtered to
    ``corpus_root`` (the COMMITTED semantic wiki — an uncommitted page is then NOT verified)."""
    if files is None:
        root = repo / corpus_root
        if not root.is_dir():
            return SemanticClaims(claims=(), skipped=())
        pages = sorted(
            p.relative_to(repo).as_posix() for p in root.rglob("*.md") if p.is_file()
        )
    else:
        prefix = corpus_root.rstrip("/") + "/"
        pages = sorted(
            f for f in files if f.endswith(".md") and (f == corpus_root or f.startswith(prefix))
        )

    claims: list[StructuralClaim] = []
    skipped: list[str] = []

    for source in pages:
        try:
            text = (repo / source).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(source)
            continue
        parsed_page = _parse_markdown_claims(source, text, strict=False)
        claims.extend(parsed_page.claims)
    return SemanticClaims(claims=tuple(claims), skipped=tuple(sorted(skipped)))


def extract_live_doc_anchor_claims(
    repo: Path,
    files: tuple[str, ...],
    patterns: tuple[str, ...],
) -> SemanticClaims:
    claims: list[StructuralClaim] = []
    malformed: list[MalformedClaim] = []
    skipped: list[str] = []
    for source in live_doc_anchor_files(files, patterns):
        try:
            text = (repo / source).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(source)
            continue
        if source.endswith(".html"):
            parsed_page = _parse_html_claims(source, text, strict=True)
        else:
            parsed_page = _parse_markdown_claims(source, text, strict=True)
        claims.extend(parsed_page.claims)
        malformed.extend(parsed_page.malformed)
    claims.sort(key=lambda claim: (claim.source, claim.line, claim.kind, claim.subject, claim.object))
    malformed.sort(key=lambda item: (item.source, item.line, item.detail))
    return SemanticClaims(tuple(claims), tuple(sorted(skipped)), tuple(malformed))

def _parse_markdown_claims(source: str, text: str, strict: bool) -> SemanticClaims:
    claims: list[StructuralClaim] = []
    malformed: list[MalformedClaim] = []
    in_claim = False
    claim_fence_len = 0
    outer_fence_len = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        fence_len, info = _backtick_fence(stripped)
        if outer_fence_len:
            if fence_len >= outer_fence_len and not info:
                outer_fence_len = 0
            continue
        if not in_claim:
            if fence_len:
                if info == "atlas:claims":
                    in_claim = True
                    claim_fence_len = fence_len
                else:
                    outer_fence_len = fence_len
            continue
        if fence_len >= claim_fence_len and not info:
            in_claim = False
            claim_fence_len = 0
            continue
        _append_claim(claims, malformed, source, lineno, stripped, strict)
    if strict and in_claim:
        malformed.append(MalformedClaim(source, len(text.splitlines()) or 1, "unterminated atlas:claims block"))
    return SemanticClaims(tuple(claims), (), tuple(malformed))


def _backtick_fence(stripped: str) -> tuple[int, str]:
    if not stripped.startswith("```"):
        return (0, "")
    count = 0
    for char in stripped:
        if char != "`":
            break
        count += 1
    if count < 3:
        return (0, "")
    return (count, stripped[count:].strip())


def _parse_html_claims(source: str, text: str, strict: bool) -> SemanticClaims:
    parser = _AtlasClaimsHtmlParser()
    parser.feed(text)
    parser.close()
    claims: list[StructuralClaim] = []
    malformed: list[MalformedClaim] = []
    for lineno, raw in parser.claim_lines():
        _append_claim(claims, malformed, source, lineno, raw.strip(), strict)
    return SemanticClaims(tuple(claims), (), tuple(malformed))


class _AtlasClaimsHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._active = False
        self._chunks: list[tuple[int, str]] = []
        self._blocks: list[list[tuple[int, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "pre":
            return
        if any(key == "data-atlas-claims" for key, _value in attrs):
            self._active = True
            self._chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre" and self._active:
            self._blocks.append(self._chunks)
            self._active = False
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._active:
            self._chunks.append((self.getpos()[0], data))

    def claim_lines(self) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for chunks in self._blocks:
            for start_line, data in chunks:
                for offset, line in enumerate(data.splitlines()):
                    out.append((start_line + offset, line))
        return out


def _append_claim(
    claims: list[StructuralClaim],
    malformed: list[MalformedClaim],
    source: str,
    lineno: int,
    line: str,
    strict: bool,
) -> None:
    if not line:
        return
    parsed = _parse_claim(line)
    if parsed is None:
        if strict:
            malformed.append(MalformedClaim(source, lineno, line))
        return
    kind, subject, obj, concept = parsed
    claims.append(
        StructuralClaim(
            source=source,
            line=lineno,
            kind=kind,
            subject=subject,
            object=obj,
            concept=concept,
        )
    )


def _parse_claim(line: str):
    """``<kind>: ...`` -> (kind, subject, object, concept) or None if malformed."""
    kind, sep, rest = line.partition(":")
    kind = kind.strip()
    if not sep or kind not in _KINDS:
        return None
    rest = rest.strip()
    if kind == "defines":
        concept, sep2, target = rest.rpartition(" -> ")
        subject = _norm_node(target)
        concept = concept.strip()
        if not sep2 or not subject or not concept:
            return None
        return ("defines", subject, "", concept)
    if kind == "calls":
        left, sep2, right = rest.rpartition(" -> ")
        subject = _norm_node(left)
        obj = _norm_node(right)
        if not sep2 or not subject or not obj:
            return None
        return ("calls", subject, obj, "")
    subject = _norm_node(rest)  # contains
    if not subject:
        return None
    return ("contains", subject, "", "")


def _norm_node(text: str) -> str:
    """Normalize a node-id; return ``""`` if it is not a well-formed address. A node-id is
    a bare repo-rel path (a module/package node, no ``::``) or ``<path>::<class>::<symbol>``
    (count("::")==2). A leading ``./`` is stripped; a path that escapes the repo is rejected."""
    node = text.strip().replace("\\", "/")
    while node.startswith("./"):
        node = node[2:]
    if not node or node == "." or node.count("::") not in (0, 2):
        return ""
    path = node.split("::", 1)[0]
    if not path:
        return ""
    # Reject a path that escapes the repo, even via interior traversal
    # (`a/../../etc`): node-ids are only dict-lookup keys here, never opened, but keep the
    # grammar tight. normpath collapses the segments so the escape is visible.
    norm = posixpath.normpath(path)
    if norm == "." or norm == ".." or norm.startswith("../"):
        return ""
    return node
