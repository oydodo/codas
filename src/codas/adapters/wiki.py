from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

from codas.adapters.markdown import KNOWN_EXTS, _candidates, _resolve

WIKI_ROOT_DEFAULT = ".codas/wiki"
# Hand-authored Atlas code-wiki pages (advisory prose + verified code anchors). Their
# PROSE must never enter the byte-identical inventory hash, so extract_wiki_claims and the
# markdown doc_claims scan both SKIP this subtree; only extract_code_anchor_claims reads it
# (position-stripped, policy-time, not serialized into inventory).
CODE_ROOT_DEFAULT = ".codas/wiki/code"

# Section heading (lowercased) -> claim kind for path refs found under it.
_SECTION_KIND = {
    "canonical sources": "canonical_source",
    "concepts": "concept_page",
    "required synchronization": "sync_target",
}
_EVIDENCE_LABEL = "evidence:"  # inline label line inside concept pages
# Like markdown._PATH_RE but also allows '*' so glob refs (.trellis/tasks/**) pass.
_WIKI_PATH_RE = re.compile(r"^[\w./*-]+$")


@dataclass(frozen=True)
class WikiClaim:
    source: str
    line: int
    concept: str
    kind: str  # canonical_source | concept_page | evidence | sync_target
    path: str
    path_kind: str  # literal | glob
    exists: bool


@dataclass(frozen=True)
class WikiClaims:
    claims: tuple[WikiClaim, ...]
    skipped: tuple[str, ...]


def extract_wiki_claims(
    repo: Path, files: tuple[str, ...], wiki_root: str = WIKI_ROOT_DEFAULT
) -> WikiClaims:
    """Parse structured path assertions from the Atlas Wiki markdown.

    A wiki page asserts path references in a structural role recoverable from the
    page's section layout: ``## Canonical Sources`` -> ``canonical_source``,
    ``## Concepts`` links -> ``concept_page``, an ``Evidence:`` label -> ``evidence``
    for the following code-span paths, ``## Required Synchronization`` ->
    ``sync_target``. References in unrecognized sections are left to ``doc_claims`` /
    ``stale_claim``. Scoped to ``.md`` under ``wiki_root``; fence-aware and
    deterministic (stable sort). Index only — verification is the D2 policy.
    """
    prefix = wiki_root.rstrip("/") + "/"
    code_prefix = CODE_ROOT_DEFAULT.rstrip("/") + "/"
    wiki_files = [
        f
        for f in files
        if f.endswith(".md")
        and (f == wiki_root or f.startswith(prefix))
        and not f.startswith(code_prefix)  # code-wiki prose stays out of the hash
    ]
    claims: list[WikiClaim] = []
    skipped: list[str] = []
    seen: set[tuple[str, int, str, str]] = set()

    for source in sorted(wiki_files):
        try:
            text = (repo / source).read_text(errors="ignore")
        except OSError:
            skipped.append(source)
            continue
        concept = _concept_slug(source)
        section: str | None = None
        in_evidence = False
        in_fence = False
        for lineno, raw in enumerate(text.splitlines(), start=1):
            stripped = raw.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            heading = _heading(stripped)
            if heading is not None:
                section = _SECTION_KIND.get(heading)
                in_evidence = False
                continue
            if stripped.lower() == _EVIDENCE_LABEL:
                in_evidence = True
                continue
            kind = "evidence" if in_evidence else section
            if kind is None:
                continue
            # concept_page is asserted by links; the path-list kinds by code spans.
            want = "link" if kind == "concept_page" else "code"
            for cand_kind, candidate in _candidates(raw):
                if cand_kind != want:
                    continue
                normalized = _wiki_normalize(candidate, cand_kind)
                if normalized is None:
                    continue
                raw_path, _fragment = normalized
                path = _resolve(repo, source, raw_path, cand_kind)
                if path is None:  # escapes the repo
                    continue
                path_kind = "glob" if "*" in path else "literal"
                exists = _exists(repo, path, path_kind)
                # The slash-only code-span gate is permissive enough to catch
                # prose like `read/write`. Keep a claim only when it is a genuine
                # path reference: a known extension, a glob, or something that
                # actually resolves on disk. Extensioned/glob refs are kept even
                # when missing so the D2 policy can flag them stale.
                if not (path.endswith(KNOWN_EXTS) or path_kind == "glob" or exists):
                    continue
                key = (source, lineno, kind, path)
                if key in seen:
                    continue
                seen.add(key)
                claims.append(
                    WikiClaim(
                        source=source,
                        line=lineno,
                        concept=concept,
                        kind=kind,
                        path=path,
                        path_kind=path_kind,
                        exists=exists,
                    )
                )

    claims.sort(key=lambda c: (c.source, c.line, c.kind, c.path))
    return WikiClaims(claims=tuple(claims), skipped=tuple(sorted(skipped)))


def _wiki_normalize(candidate: str, kind: str) -> tuple[str, str] | None:
    """Like ``markdown._normalize`` but wiki-permissive.

    A code span needs only a slash to qualify (bare directories, extensionless
    scripts and globs are all legitimate wiki path references), and ``*`` is an
    allowed path character so glob refs pass the shape gate.
    """
    text = candidate.strip().replace("\\", "/")
    if not text or "://" in text or text.startswith("#") or text.startswith("mailto:"):
        return None
    head, _, fragment = text.partition("#")  # path?query#fragment
    path, _, _query = head.partition("?")
    if not path or " " in path or "\t" in path or not _WIKI_PATH_RE.match(path):
        return None

    has_slash = "/" in path
    has_ext = path.endswith(KNOWN_EXTS)
    if kind == "code":
        if not has_slash:  # any slashed path: dir, extensionless, glob, file
            return None
    elif not (has_ext or has_slash):  # link
        return None

    return path, fragment


def _exists(repo: Path, path: str, path_kind: str) -> bool:
    if path_kind == "glob":
        try:
            return any(True for _ in repo.glob(path))
        except ValueError:
            # Malformed glob (e.g. '**' not an entire path component) -> the wiki
            # cites an unverifiable pattern; record it as not-found, never crash.
            return False
    return (repo / path).exists()


def _concept_slug(source: str) -> str:
    return posixpath.splitext(posixpath.basename(source))[0]


def _heading(stripped: str) -> str | None:
    if not stripped.startswith("#"):
        return None
    return stripped.strip("#").strip().lower()  # tolerate trailing ATX '#'


# --- generated-page atlas:claims (D3d) ------------------------------------------

GENERATED_ROOT_DEFAULT = ".codas/wiki/generated"


@dataclass(frozen=True)
class GeneratedClaim:
    source: str
    line: int
    kind: str  # unit | roadmap
    subject: str
    value: str


@dataclass(frozen=True)
class GeneratedPage:
    source: str
    source_inventory_hash: str  # "" if absent
    claims: tuple[GeneratedClaim, ...]
    has_block: bool


@dataclass(frozen=True)
class GeneratedClaims:
    pages: tuple[GeneratedPage, ...]
    skipped: tuple[str, ...]


# --- code-wiki atlas:claims (W1) ------------------------------------------------


@dataclass(frozen=True)
class CodeAnchorClaim:
    """One ``anchor_symbol`` claim from a hand-authored code-wiki page: the page asserts
    that ``concept`` is defined by symbol ``name`` in ``path``. ``line`` is for human
    evidence display only — it is NOT part of the claim identity (the claim is the
    assertion, not its byte position), so a prose edit that shifts lines does not change
    the policy-time fact."""

    source: str
    line: int
    concept: str
    path: str
    name: str


@dataclass(frozen=True)
class CodeAnchorClaims:
    claims: tuple[CodeAnchorClaim, ...]
    skipped: tuple[str, ...]


def extract_code_anchor_claims(
    repo: Path, files: tuple[str, ...], code_root: str = CODE_ROOT_DEFAULT
) -> CodeAnchorClaims:
    """Parse ``anchor_symbol:`` lines from the fenced ``atlas:claims`` block of each
    hand-authored code-wiki page under ``code_root``.

    Grammar (one anchor per line, inside a ```` ```atlas:claims ```` fence)::

        anchor_symbol: <concept> -> <repo-rel path>:<symbol name>

    Robust like :func:`extract_generated_claims` — a malformed line is skipped, never a
    crash: split the concept from the target on the LAST `` -> `` (``rpartition``) so a
    concept may itself contain `` -> ``; split the target into (path, name) on the LAST
    ``:`` so a path may contain none. Backslashes are normalized to ``/``; a leading
    ``./`` is stripped; an empty concept/path/name or a path that escapes the repo (``..``)
    is rejected. The ``symbols`` family these anchors resolve against is OPEN-world, so the
    consuming policy treats a non-resolving anchor as a WARNING, never an error.
    Deterministic: pages sorted by source, claims in file order.
    """
    prefix = code_root.rstrip("/") + "/"
    code_files = [
        f for f in files if f.endswith(".md") and (f == code_root or f.startswith(prefix))
    ]
    claims: list[CodeAnchorClaim] = []
    skipped: list[str] = []

    for source in sorted(code_files):
        try:
            text = (repo / source).read_text(errors="ignore")
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
            if not stripped.startswith("anchor_symbol:"):
                continue
            parsed = _parse_anchor_symbol(stripped.split(":", 1)[1])
            if parsed is None:
                continue  # malformed -> skip, never crash
            concept, path, name = parsed
            claims.append(
                CodeAnchorClaim(
                    source=source, line=lineno, concept=concept, path=path, name=name
                )
            )
    return CodeAnchorClaims(claims=tuple(claims), skipped=tuple(sorted(skipped)))


def _parse_anchor_symbol(rest: str):
    """``<concept> -> <path>:<name>`` -> (concept, path, name) or None if malformed."""
    concept, sep, target = rest.rpartition(" -> ")
    if not sep:
        return None
    concept = concept.strip()
    path_part, sep2, name = target.rpartition(":")
    if not sep2:
        return None
    path = path_part.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    name = name.strip()
    if not concept or not path or not name:
        return None
    if path == ".." or path.startswith("../"):
        return None
    return concept, path, name


def extract_generated_claims(
    repo: Path, files: tuple[str, ...], generated_root: str = GENERATED_ROOT_DEFAULT
) -> GeneratedClaims:
    """Parse the fenced ``atlas:claims`` block of each committed generated page.

    The deliberate INVERSE of ``extract_wiki_claims``: that skips fenced content (so a
    generated page's atlas:claims block produces no wiki_claims and stays dogfood-clean
    for ``stale_wiki_claim``), while this reads INSIDE the ``atlas:claims`` fence.
    Scoped to ``.md`` under ``generated_root``. Recognizes ``source_inventory_hash:
    <h>``, ``unit: <subject> -> <value>`` and ``roadmap: <subject> -> <value>`` lines —
    the format ``app/wiki.render_generated_overview`` emits. Deterministic (pages sorted
    by source, claims in file order). The ``generated_wiki_drift`` policy verifies these.
    """
    prefix = generated_root.rstrip("/") + "/"
    gen_files = [
        f
        for f in files
        if f.endswith(".md") and (f == generated_root or f.startswith(prefix))
    ]
    pages: list[GeneratedPage] = []
    skipped: list[str] = []

    for source in sorted(gen_files):
        try:
            text = (repo / source).read_text(errors="ignore")
        except OSError:
            skipped.append(source)
            continue
        has_block = False
        source_hash = ""
        claims: list[GeneratedClaim] = []
        in_block = False
        for lineno, raw in enumerate(text.splitlines(), start=1):
            stripped = raw.strip()
            if not in_block:
                if stripped.startswith("```") and stripped[3:].strip() == "atlas:claims":
                    in_block = True
                    has_block = True
                continue
            if stripped.startswith("```"):
                in_block = False
                continue
            if stripped.startswith("source_inventory_hash:"):
                if not source_hash:
                    source_hash = stripped.split(":", 1)[1].strip()
                continue
            for kind in ("unit", "roadmap"):
                if stripped.startswith(kind + ":"):
                    _, _, rest = stripped.partition(":")
                    subject, sep, value = rest.partition(" -> ")
                    if sep:
                        claims.append(
                            GeneratedClaim(
                                source=source,
                                line=lineno,
                                kind=kind,
                                subject=subject.strip(),
                                value=value.strip(),
                            )
                        )
                    break
        pages.append(
            GeneratedPage(
                source=source,
                source_inventory_hash=source_hash,
                claims=tuple(claims),
                has_block=has_block,
            )
        )
    return GeneratedClaims(pages=tuple(pages), skipped=tuple(sorted(skipped)))
