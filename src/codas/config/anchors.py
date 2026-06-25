from __future__ import annotations

import fnmatch

LIVE_DOC_EXCLUDE_PREFIXES = (
    ".trellis/tasks/archive/",
    ".trellis/workspace/",
)
LIVE_DOC_EXTENSIONS = (".md", ".html")


def unsupported_live_doc_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        pattern
        for pattern in patterns
        if not pattern.endswith(LIVE_DOC_EXTENSIONS)
    )


def live_doc_anchor_files(files: tuple[str, ...], patterns: tuple[str, ...]) -> tuple[str, ...]:
    supported = tuple(
        pattern for pattern in patterns if pattern not in unsupported_live_doc_patterns((pattern,))
    )
    out = []
    for path in files:
        cleaned = path.replace("\\", "/")
        if _excluded_live_doc(cleaned) or not cleaned.endswith(LIVE_DOC_EXTENSIONS):
            continue
        if any(fnmatch.fnmatch(cleaned, pattern) for pattern in supported):
            out.append(cleaned)
    return tuple(sorted(set(out)))


def _excluded_live_doc(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in LIVE_DOC_EXCLUDE_PREFIXES)
