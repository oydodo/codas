from __future__ import annotations

import subprocess
from pathlib import Path


def extract_changed_paths(repo: Path) -> tuple[str, ...]:
    """Working-tree paths that differ from HEAD (tracked diff ∪ untracked).

    Repo-relative posix, sorted and de-duplicated. The diff substrate for the
    ``spec_drift`` policy: it answers "which files changed since the last commit",
    the deterministic half of drift detection (the host agent judges *how* a change
    is material from the actual diff content; Codas only grounds *which* files moved).

    Returns ``()`` when git is unavailable, the path is not a repository, or ``HEAD``
    does not resolve (a repo with no commits has no baseline, so there is no drift to
    compute). Deterministic given the current tree state — ordering is imposed by
    ``sorted`` here, not by git.

    Intentionally **not** part of ``codas inventory``: it reflects dirty working-tree
    state and would break the byte-identical inventory invariant. It is surfaced only
    as a policy-time fact via ``ScanContext.changed_paths()``.
    """
    tracked = _git_lines(
        repo, ["diff", "-z", "--name-only", "--no-renames", "HEAD"]
    )
    untracked = _git_lines(
        repo, ["ls-files", "-z", "--others", "--exclude-standard"]
    )
    if tracked is None or untracked is None:
        return ()
    paths = {path.replace("\\", "/") for path in tracked + untracked if path}
    return tuple(sorted(paths))


def list_python_paths_at_head(repo: Path) -> tuple[tuple[str, str], ...] | None:
    """``.py`` blobs at ``HEAD`` as ``(repo-rel path, blob sha)``, sorted by path.

    Lists the committed tree (``git ls-tree -r -z HEAD``), keeping only ``blob``
    entries ending in ``.py`` — submodules (``commit`` entries) and trees are
    dropped; a ``.py`` symlink (still a blob) is the one parity edge (git stores the
    link text, a working-tree read would follow it) and is negligible for real
    source. Returns the blob SHA per path (the future fact-cache key, so this read
    path is cache-ready). ``None`` when ``HEAD`` does not resolve (no commits) or the
    path is not a git repository — the caller treats that as "no baseline".

    Sorted here rather than trusting git's tree order, keeping determinism local.
    """
    chunks = _git_lines(repo, ["ls-tree", "-r", "-z", "HEAD"])
    if chunks is None:
        return None
    entries: list[tuple[str, str]] = []
    for chunk in chunks:
        meta, _, path = chunk.partition("\t")
        if not path or not path.endswith(".py"):
            continue
        parts = meta.split()  # "<mode> <type> <sha>"
        if len(parts) != 3 or parts[1] != "blob":
            continue
        entries.append((path.replace("\\", "/"), parts[2]))
    return tuple(sorted(entries))


def read_blob_at_head(repo: Path, blob_sha: str) -> str | None:
    """Decode a git blob by sha, ``utf-8`` with ``errors="ignore"``.

    The decode rule matches :func:`codas.adapters.python_parse.parse_python_modules`
    (which reads working-tree bytes the same way), so a ``HEAD`` snapshot and the
    working-tree snapshot are parsed from text decoded identically — a clean tree
    yields an empty fact delta rather than spurious differences from a codec mismatch.
    ``None`` on any git failure; the caller abandons the whole snapshot rather than
    treating a read miss as a deleted file (which would read as false "removed" facts).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", blob_sha],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.decode("utf-8", "ignore")


def _git_lines(repo: Path, args: list[str]) -> list[str] | None:
    """Run a NUL-delimited git command; split on ``\\0``. ``None`` on failure.

    ``-z`` keeps paths with spaces, tabs or newlines intact (line-splitting would
    corrupt them), so the result is faithful and deterministic.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [chunk for chunk in result.stdout.split("\0") if chunk]
