from __future__ import annotations

import fnmatch
from html.parser import HTMLParser
from pathlib import Path

from codas.adapters.markdown import DocClaim, _normalize, _resolve

# Govern authoritative/supporting `.html` docs (Layer 1: path/link existence). HTML is a
# governance black hole today — the markdown adapter scans `.md` only, so a path
# reference in an authoritative `.html` spec drifts unseen. This extracts repo-relative
# path claims (from `<code>` spans and `<a href>`) and feeds them to `stale_html_claim`,
# parity with the markdown `doc_claims` -> `stale_claim` path. Reuses the markdown
# normalize/resolve/keep-filter by intra-`codas-adapters`-unit import (as `wiki.py` does,
# so the path-shape gate is ONE definition, not a duplicated helper). Deterministic
# (stdlib `html.parser`, sorted output); no LLM.


def governed_html_files(files: tuple[str, ...], patterns: tuple[str, ...]) -> list[str]:
    """The ``.html`` files in the scanned set that a config constraint-source pattern
    governs. A constraint source may be a glob, so match with ``fnmatch`` (like
    ``config_sources``/``document_set``) rather than exact-compare; a
    leading ``./`` is normalized on both sides. (``fnmatch`` ``*`` spans ``/``, and ``**``
    requires >=1 intermediate segment — ``docs/*.html`` matches ``docs/page.html`` whereas
    ``docs/**/*.html`` matches only ``docs/sub/page.html``.) Arbitrary ungoverned ``.html`` (a fixture,
    a vendored report) is excluded. Distinctly named (not ``_matches_any``, which exists
    in ``document_set`` -> the ``duplicate_implementation`` trap)."""
    norm_patterns = [_strip_dot_slash(pattern) for pattern in patterns]
    out = [
        path
        for path in files
        if path.endswith(".html")
        and any(fnmatch.fnmatch(_strip_dot_slash(path), pattern) for pattern in norm_patterns)
    ]
    return sorted(set(out))


def _strip_dot_slash(path: str) -> str:
    cleaned = path.replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def extract_html_claims(repo: Path, files: list[str]) -> list[DocClaim]:
    """Path/link claims from the given (already config-scoped) ``.html`` files.

    Mirrors markdown code/link extraction: a `<code>` span is the ``code`` kind, an
    `<a href>` the ``link`` kind, each run through the shared ``_normalize``/``_resolve``
    path-shape gate. `<pre>` blocks are illustrative examples (the HTML analogue of a
    markdown fenced block) and excluded. Deterministic: dedup on the identity key, total
    sort.
    """
    claims: list[DocClaim] = []
    seen: set[tuple[str, int, str, str, str]] = set()
    for source in sorted(files):
        # Explicit utf-8 (not the locale default) so html_claims — which enter the
        # byte-identical inventory — are reproducible cross-platform (matches the v2-A
        # python_parse decode fix).
        text = (repo / source).read_text(encoding="utf-8", errors="ignore")
        parser = _ClaimParser()
        parser.feed(text)
        parser.close()
        for line, kind, raw in parser.claim_refs():
            normalized = _normalize(raw, kind)
            if normalized is None:
                continue
            raw_path, fragment = normalized
            path = _resolve(repo, source, raw_path, kind)
            if path is None:  # escapes the repo
                continue
            key = (source, line, path, fragment, kind)
            if key in seen:
                continue
            seen.add(key)
            claims.append(
                DocClaim(
                    source=source,
                    line=line,
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


class _ClaimParser(HTMLParser):
    """Collect `<code>`-span and `<a href>` path references with positions, then drop any
    that fall inside a CLOSED `<pre>...</pre>` block (illustrative example, not a claim).

    Suppression is POSITIONAL against closed `<pre>` ranges, not a running depth counter:
    an unclosed `<pre>` (malformed HTML) yields no range, so it does NOT silently suppress
    every later claim in the same file (codex impl-review SHOULD-FIX). A stray `</pre>`
    with no open is ignored; nested `<pre>` is handled by the stack.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._pre_stack: list[tuple[int, int]] = []  # positions of open <pre>
        self._pre_ranges: list[tuple[tuple[int, int], tuple[int, int]]] = []  # closed pre spans
        self._in_code = False
        self._buf: list[str] = []
        self._code_pos = (0, 0)
        self._raw: list[tuple[tuple[int, int], str, str]] = []  # (pos, kind, raw)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "pre":
            self._pre_stack.append(self.getpos())
        elif tag == "code":
            self._in_code = True
            self._buf = []
            self._code_pos = self.getpos()
        elif tag == "a":
            self._emit_href(attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._emit_href(attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre" and self._pre_stack:
            start = self._pre_stack.pop()
            self._pre_ranges.append((start, self.getpos()))
        elif tag == "code" and self._in_code:
            self._in_code = False
            self._raw.append((self._code_pos, "code", "".join(self._buf)))

    def handle_data(self, data: str) -> None:
        if self._in_code:
            self._buf.append(data)

    def _emit_href(self, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key == "href" and value:
                self._raw.append((self.getpos(), "link", value))

    def claim_refs(self) -> list[tuple[int, str, str]]:
        """(line, kind, raw) for each reference NOT inside a closed `<pre>` range, in
        document order. (line, col) positions compare lexicographically within a file."""
        out: list[tuple[int, str, str]] = []
        for pos, kind, raw in self._raw:
            if any(start <= pos <= end for start, end in self._pre_ranges):
                continue
            out.append((pos[0], kind, raw))
        return out
