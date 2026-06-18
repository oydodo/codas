from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

from codas.adapters.markdown import KNOWN_EXTS, _candidates, _resolve

WIKI_ROOT_DEFAULT = ".codas/wiki"

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
    wiki_files = [
        f for f in files if f.endswith(".md") and (f == wiki_root or f.startswith(prefix))
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
