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
