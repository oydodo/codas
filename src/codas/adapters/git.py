from __future__ import annotations

import subprocess
from pathlib import Path


def extract_changed_paths(repo: Path, base: str = "HEAD") -> tuple[str, ...]:
    """Working-tree paths that differ from ``base`` (tracked diff ∪ untracked).

    Repo-relative posix, sorted and de-duplicated. The diff substrate for the
    ``fact_coupling`` policy (``base="HEAD"``): it answers "which files changed since
    the last commit", the companion to the fact delta — a coupling fires when a watched
    fact-delta is nonempty but a required companion path is absent from this changed-path
    set.

    ``base`` is the diff baseline. Defaulting to ``HEAD`` gives the working-tree diff;
    passing an earlier ref (a session BASELINE sha) gives everything changed SINCE that
    ref — committed AND uncommitted — which is how ``codas status --since`` sees changes
    a worker already committed before returning (the working tree may be clean against
    ``HEAD`` yet dirty against the baseline).

    Returns ``()`` when git is unavailable, the path is not a repository, or ``base``
    does not resolve (a repo with no commits has no baseline, so there is no drift to
    compute). Deterministic given the current tree state — ordering is imposed by
    ``sorted`` here, not by git.

    Intentionally **not** part of ``codas inventory``: it reflects dirty working-tree
    state and would break the byte-identical inventory invariant. It is surfaced only
    as a policy-time fact via ``ScanContext.changed_paths()`` / ``changed_since()``.
    """
    tracked = _git_lines(
        repo, ["diff", "-z", "--name-only", "--no-renames", base]
    )
    untracked = _git_lines(
        repo, ["ls-files", "-z", "--others", "--exclude-standard"]
    )
    if tracked is None or untracked is None:
        return ()
    paths = {path.replace("\\", "/") for path in tracked + untracked if path}
    return tuple(sorted(paths))


def head_commit(repo: Path) -> str | None:
    """The resolved ``HEAD`` commit sha, or ``None`` when ``repo`` is not a git
    repository or ``HEAD`` does not resolve (no commits yet).

    Used to (a) DISTINGUISH "clean tree" from "no git baseline" in ``codas status``
    (an installed hook that cannot diff is INERT, not silently OK), and (b) record the
    session BASELINE sha that ``--since`` diffs against. Read-only; never serialized
    into the byte-identical inventory.
    """
    lines = _git_lines(repo, ["rev-parse", "HEAD"])
    return lines[0].strip() if lines else None


def ref_resolves(repo: Path, ref: str) -> bool:
    """True if ``ref`` resolves to a commit. Distinguishes a STALE/orphaned ``--since``
    baseline (after a rebase/squash/amend, or a garbage ref) from a genuinely clean tree:
    both make ``extract_changed_paths(base=ref)`` return ``()``, but only the former should
    be surfaced as a degraded ``codas status`` (the committed-worker changes silently vanish).
    """
    return (
        _git_lines(repo, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        is not None
    )


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
