from __future__ import annotations

import fnmatch
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import StructureMap, StructureUnit

GLOB_CHARS = ("*", "?", "[")
_IGNORE_DIRS = {".git", "__pycache__"}
# Generated/local-cache subtrees pruned on the non-git walk fallback (the git path
# already excludes them via .gitignore / --exclude-standard). Keeps receipts and the
# regenerable local cache (e.g. the W3 semantic corpus under .codas/cache/semantic/) out
# of the scan so check/inventory stay deterministic REGARDLESS of git availability — the
# corpus-out-of-hash guarantee then holds unconditionally, not only in a git repo.
_IGNORE_PATHS = {".codas/receipts", ".codas/cache"}

# Default reserved prefix for Codas-RENDERED committed output — scanned NEVER as input.
# Distinct from _IGNORE_PATHS (local/regenerable cache + receipts, walk-only): the wiki/
# book is COMMITTED but DERIVED (a pure render of facts + .codas/wiki/ source prose), so
# scanning it would be (a) self-referential — the book renders facts and its bytes would
# then feed the inventory hash the book pins — and (b) churn-amplifying: every prose edit
# would move the inventory hash. The reservation is honored in TWO layers: the FILE SCANNER
# (filter_to_roots, the ONE funnel shared by discover_files, head_snapshot, and the artifact
# index) AND every claim/role existence site that resolves a path -> fact (the doc/wiki/html
# adapters + the documents-role) — a governance doc referencing the book must resolve it
# ABSENT, never hit Path.exists(), or the book's on-disk presence would leak into the hash.
# W7 lifts the prefix into config (`wiki.book_root`): default keeps ("wiki",); an explicit
# empty string opts out so a user's real wiki/ docs are governed normally (no over-reach).
DERIVED_OUTPUT_DEFAULT = ("wiki",)


def derived_output_prefixes(raw: dict[str, Any]) -> tuple[str, ...]:
    """Resolve the reserved Codas-rendered output prefixes from raw config.

    Mirrors :func:`workspace_roots`: pure, reads the raw mapping, never imports the config
    layer. The single source of the reservation, threaded as DATA to the scanner and the
    claim/role existence sites so the book is dropped from EVERY scan and resolved absent by
    EVERY existence check, in one config-driven place. Resolution of ``wiki.book_root``:

      - absent / null  -> default ``("wiki",)`` (the W4a shipped reservation; a repo that
                          never declares the knob keeps its rendered book invisible to scans).
      - ``""``          -> ``()`` — explicit OPT-OUT; a user's real ``wiki/`` docs are then
                          governed normally (this is the escape hatch that dissolves over-reach).
      - ``<path>``      -> ``(<normalized path>,)``.
    """
    wiki = raw.get("wiki")
    if isinstance(wiki, dict) and "book_root" in wiki:
        root = wiki.get("book_root")
        if root is None:
            return DERIVED_OUTPUT_DEFAULT
        # normalize_path collapses `.`/`./x`/trailing-slash/backslashes to the repo-relative
        # forward-slash form used by every scanned path, so the prefix-match cannot silently
        # miss; an empty/root result is the explicit opt-out.
        text = normalize_path(str(root))
        return (text,) if text else ()
    return DERIVED_OUTPUT_DEFAULT


def is_derived_output(path: str, prefixes: tuple[str, ...]) -> bool:
    """True if ``path`` is under one of the reserved Codas-rendered output ``prefixes``.
    Prefix-boundary safe: ``wiki/`` matches ``wiki`` and ``wiki/x`` but never ``wikipedia.py``
    at root. The SINGLE authority used by the scanner AND every existence site (one predicate,
    no forked rule)."""
    return any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in prefixes
    )


def workspace_roots(raw: dict[str, Any]) -> tuple[str, ...]:
    """Resolve configured workspace roots from raw config, defaulting to ``(".",)``.

    Shared by the inventory and the file-scanning policies so the default-roots
    rule cannot fork. Pure: takes the raw mapping, never imports the config layer.
    """
    workspace = raw.get("workspace")
    if isinstance(workspace, dict):
        roots = workspace.get("roots")
        if isinstance(roots, list) and roots:
            return tuple(str(root) for root in roots)
    return (".",)


@dataclass(frozen=True)
class UnitObservation:
    unit_id: str
    exists: bool
    artifact_count: int


@dataclass(frozen=True)
class ArtifactIndex:
    files: tuple[str, ...]
    observations: dict[str, UnitObservation]
    unowned: tuple[str, ...]


def normalize_path(value: str) -> str:
    """Normalize a unit or file path to a repo-relative, forward-slash prefix.

    Root paths (``.`` / ``./`` / empty) collapse to the empty prefix, which
    matches every file as the least-specific owner.
    """
    text = value.strip().replace("\\", "/")
    if text in (".", "./", ""):
        return ""
    if text.startswith("./"):
        text = text[2:]
    return text.rstrip("/")


def _is_glob(prefix: str) -> bool:
    return any(char in prefix for char in GLOB_CHARS)


def _literal_prefix(pattern: str) -> str:
    cut = len(pattern)
    for char in GLOB_CHARS:
        found = pattern.find(char)
        if found != -1:
            cut = min(cut, found)
    return pattern[:cut].rstrip("/")


def discover_files(
    repo: Path,
    roots: tuple[str, ...],
    derived_prefixes: tuple[str, ...] = DERIVED_OUTPUT_DEFAULT,
) -> list[str]:
    files = _git_files(repo)
    if files is None:
        files = _walk_files(repo, derived_prefixes)
    return filter_to_roots(files, roots, derived_prefixes)


def filter_to_roots(
    files: list[str],
    roots: tuple[str, ...],
    derived_prefixes: tuple[str, ...] = DERIVED_OUTPUT_DEFAULT,
) -> list[str]:
    """Select the files under the configured workspace roots (sorted, unique), minus the
    reserved Codas-rendered output ``derived_prefixes`` (config-driven via
    :func:`derived_output_prefixes`; defaults to ``("wiki",)`` so a config-less caller keeps
    the shipped reservation).

    Public so any scan that builds its own file list off-disk — e.g. the
    ``HEAD`` fact snapshot reading ``git ls-tree`` — applies the IDENTICAL root
    AND derived-output discipline as :func:`discover_files`, rather than re-implementing
    it. This is the single chokepoint where the ``wiki/`` book is dropped from EVERY scan.
    """
    norm_roots = [normalize_path(root) for root in roots] or [""]
    selected: set[str] = set()
    for path in files:
        if is_derived_output(path, derived_prefixes):
            continue
        for root in norm_roots:
            if root == "" or path == root or path.startswith(root + "/"):
                selected.add(path)
                break
    return sorted(selected)


def _git_files(repo: Path) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [line.replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _walk_files(
    repo: Path, derived_prefixes: tuple[str, ...] = DERIVED_OUTPUT_DEFAULT
) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _IGNORE_DIRS
            and (Path(dirpath) / name).relative_to(repo).as_posix() not in _IGNORE_PATHS
            and not is_derived_output(
                (Path(dirpath) / name).relative_to(repo).as_posix(), derived_prefixes
            )
        ]
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            rel = (Path(dirpath) / name).relative_to(repo).as_posix()
            files.append(rel)
    return files


def build_artifact_index(
    repo: Path,
    roots: tuple[str, ...],
    structure_map: StructureMap,
    files: list[str] | None = None,
    derived_prefixes: tuple[str, ...] = DERIVED_OUTPUT_DEFAULT,
) -> ArtifactIndex:
    if files is None:
        files = discover_files(repo, roots, derived_prefixes)
    else:
        files = filter_to_roots(files, roots, derived_prefixes)

    literal_units: list[tuple[str, StructureUnit]] = []
    glob_units: list[tuple[str, StructureUnit]] = []
    for unit in structure_map.units:
        prefix = normalize_path(unit.path)
        if _is_glob(prefix):
            glob_units.append((prefix, unit))
        else:
            literal_units.append((prefix, unit))

    counts: dict[str, int] = {unit.id: 0 for unit in structure_map.units}
    unowned: list[str] = []

    for path in files:
        owner = _owning_unit(path, literal_units, glob_units)
        if owner is None:
            unowned.append(path)
        for prefix, unit in literal_units:
            if _matches(path, prefix):
                counts[unit.id] += 1
        for pattern, unit in glob_units:
            if fnmatch.fnmatch(path, pattern):
                counts[unit.id] += 1

    observations: dict[str, UnitObservation] = {}
    for unit in structure_map.units:
        prefix = normalize_path(unit.path)
        if _is_glob(prefix):
            exists = any(fnmatch.fnmatch(path, prefix) for path in files)
        elif prefix == "":
            exists = True
        elif is_derived_output(prefix, derived_prefixes):
            # A literal structure unit pointing at the reserved book root resolves ABSENT
            # without touching disk — the book is scanner-invisible, so its on-disk presence
            # must never flip a unit's observed.exists into the byte-identical inventory.
            # Inert today (no unit declares the book path; registration is config-only), but
            # guarded preemptively so the existence layer has no unprotected Path.exists().
            exists = False
        else:
            exists = (repo / prefix).exists()
        observations[unit.id] = UnitObservation(unit.id, exists, counts[unit.id])

    return ArtifactIndex(
        files=tuple(files),
        observations=observations,
        unowned=tuple(sorted(unowned)),
    )


def _matches(path: str, prefix: str) -> bool:
    return prefix == "" or path == prefix or path.startswith(prefix + "/")


def _owning_unit(
    path: str,
    literal_units: list[tuple[str, StructureUnit]],
    glob_units: list[tuple[str, StructureUnit]],
) -> StructureUnit | None:
    best: StructureUnit | None = None
    best_len = -1
    for prefix, unit in literal_units:
        if _matches(path, prefix) and len(prefix) > best_len:
            best_len = len(prefix)
            best = unit
    for pattern, unit in glob_units:
        if fnmatch.fnmatch(path, pattern):
            specificity = len(_literal_prefix(pattern))
            if specificity > best_len:
                best_len = specificity
                best = unit
    return best
