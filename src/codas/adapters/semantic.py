from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path

# The W3 OFFLINE semantic corpus: host-agent-generated prose pages under
# `.codas/cache/semantic/` (gitignored, regenerable, LOCAL — NOT discovered into the
# inventory, so it never perturbs the byte-identical hash). Each page MAY carry a fenced
# ```atlas:claims block of STRUCTURAL claims the deterministic calibrator (app/calibrate.py)
# tiers against facts. This adapter only PARSES claims (§17 — it makes no world/tier
# judgment, runs no model). Read DIRECTLY from disk: the corpus is gitignored, so it is NOT
# in ScanContext.files — the directory is globbed from the repo root instead.

CORPUS_ROOT_DEFAULT = ".codas/cache/semantic"

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
class SemanticClaims:
    claims: tuple[StructuralClaim, ...]
    skipped: tuple[str, ...]


def extract_semantic_claims(
    repo: Path, corpus_root: str = CORPUS_ROOT_DEFAULT
) -> SemanticClaims:
    """Parse structural claims from the fenced ``atlas:claims`` block of each ``.md`` page
    under ``corpus_root`` (read directly from disk; the corpus is gitignored). Robust like
    the W1 anchor reader — a malformed line is skipped, never a crash. Deterministic: pages
    sorted by source, claims in file order. utf-8 pinned."""
    root = repo / corpus_root
    if not root.is_dir():
        return SemanticClaims(claims=(), skipped=())

    pages = sorted(
        p.relative_to(repo).as_posix() for p in root.rglob("*.md") if p.is_file()
    )
    claims: list[StructuralClaim] = []
    skipped: list[str] = []

    for source in pages:
        try:
            text = (repo / source).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(source)
            continue
        in_block = False
        for lineno, raw in enumerate(text.splitlines(), start=1):
            stripped = raw.strip()
            if not in_block:
                if stripped.startswith("```") and stripped[3:].strip() == "atlas:claims":
                    in_block = True
                continue
            if stripped.startswith("```"):
                in_block = False
                continue
            parsed = _parse_claim(stripped)
            if parsed is None:
                continue  # malformed -> skip, never crash
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
    return SemanticClaims(claims=tuple(claims), skipped=tuple(sorted(skipped)))


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
