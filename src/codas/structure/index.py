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
# Generated-artifact subtrees pruned on the non-git walk fallback (the git path
# already excludes them via .gitignore / --exclude-standard). Keeps receipts and
# other generated files out of the scan so check/inventory stay deterministic.
_IGNORE_PATHS = {".codas/receipts"}


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


def discover_files(repo: Path, roots: tuple[str, ...]) -> list[str]:
    files = _git_files(repo)
    if files is None:
        files = _walk_files(repo)
    return _filter_to_roots(files, roots)


def _filter_to_roots(files: list[str], roots: tuple[str, ...]) -> list[str]:
    norm_roots = [normalize_path(root) for root in roots] or [""]
    selected: set[str] = set()
    for path in files:
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


def _walk_files(repo: Path) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _IGNORE_DIRS
            and (Path(dirpath) / name).relative_to(repo).as_posix() not in _IGNORE_PATHS
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
) -> ArtifactIndex:
    if files is None:
        files = discover_files(repo, roots)
    else:
        files = _filter_to_roots(files, roots)

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
