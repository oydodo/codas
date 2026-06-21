from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

KNOWN_EXTS = (".md", ".py", ".html", ".yml", ".yaml", ".json", ".toml", ".txt")
# `.codas/wiki/code/` holds hand-authored Atlas code-wiki pages whose prose is advisory
# and must NOT enter the byte-identical inventory hash (only their code anchors are read,
# position-stripped, by codas.adapters.wiki.extract_code_anchor_claims).
SKIP_PREFIXES = (
    ".trellis/tasks/",
    ".trellis/workspace/",
    ".codas/wiki/code/",
    ".codas/wiki/semantic/",  # committed semantic-wiki prose is advisory + out of the hash
)

_LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)]+)\)")
_CODE_RE = re.compile(r"`([^`]+)`")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_PATH_RE = re.compile(r"^[\w./-]+$")


@dataclass(frozen=True)
class DocClaim:
    source: str
    line: int
    path: str
    fragment: str
    kind: str  # "link" | "code"
    exists: bool


def extract_doc_claims(repo: Path, files: tuple[str, ...]) -> list[DocClaim]:
    """Extract repo-relative path references from governance Markdown docs.

    Fence-aware; normalizes each candidate (drop external/anchor, split off
    fragment) before a conservative path-shape gate. Index only — the consuming
    `stale_claim` policy is P2.
    """
    md_files = [
        f for f in files if f.endswith(".md") and not f.startswith(SKIP_PREFIXES)
    ]
    claims: list[DocClaim] = []
    seen: set[tuple[str, int, str]] = set()

    for source in sorted(md_files):
        text = (repo / source).read_text(errors="ignore")
        in_fence = False
        for lineno, raw in enumerate(text.splitlines(), start=1):
            if _FENCE_RE.match(raw):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for kind, candidate in _candidates(raw):
                normalized = _normalize(candidate, kind)
                if normalized is None:
                    continue
                raw_path, fragment = normalized
                path = _resolve(repo, source, raw_path, kind)
                if path is None:  # escapes the repo
                    continue
                key = (source, lineno, path, fragment, kind)
                if key in seen:
                    continue
                seen.add(key)
                claims.append(
                    DocClaim(
                        source=source,
                        line=lineno,
                        path=path,
                        fragment=fragment,
                        kind=kind,
                        exists=(repo / path).exists(),
                    )
                )

    claims.sort(
        key=lambda claim: (claim.source, claim.line, claim.path, claim.fragment, claim.kind)
    )
    return claims


def _candidates(line: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _LINK_RE.finditer(line):
        if match.group(1) == "!":  # image
            continue
        dest = match.group(2).strip()
        parts = dest.split()
        if parts:  # drop an optional "title" after the destination
            dest = parts[0]
        found.append(("link", dest.strip("<>")))
    for match in _CODE_RE.finditer(line):
        found.append(("code", match.group(1).strip()))
    return found


def _resolve(repo: Path, source: str, path: str, kind: str) -> str | None:
    """Resolve a reference to a repo-relative path.

    Markdown links are relative to the source file's directory; a leading `/`
    means repo root. Backtick code spans are repo-relative by convention, but
    fall back to source-relative when the repo-relative path does not exist.
    Returns None if the result escapes the repository.
    """
    if path.startswith("/"):
        resolved = posixpath.normpath(path.lstrip("/"))
    elif kind == "link":
        resolved = _join(source, path)
    else:  # code span: repo-relative, with source-relative fallback
        repo_rel = posixpath.normpath(path)
        if (repo / repo_rel).exists():
            resolved = repo_rel
        else:
            src_rel = _join(source, path)
            resolved = src_rel if (src_rel and (repo / src_rel).exists()) else repo_rel
    if not resolved or resolved == ".." or resolved.startswith("../"):
        return None
    return resolved


def _join(source: str, path: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), path))


def _normalize(candidate: str, kind: str) -> tuple[str, str] | None:
    text = candidate.strip().replace("\\", "/")
    if not text or "://" in text or text.startswith("#") or text.startswith("mailto:"):
        return None
    head, _, fragment = text.partition("#")  # path?query#fragment
    path, _, _query = head.partition("?")
    if not path or " " in path or "\t" in path or not _PATH_RE.match(path):
        return None

    has_ext = path.endswith(KNOWN_EXTS)
    has_slash = "/" in path
    if kind == "code":
        if not (has_slash and has_ext):
            return None
    elif not (has_ext or has_slash):
        return None

    return path, fragment
