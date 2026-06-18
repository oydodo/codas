from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.index import (
    build_artifact_index,
    discover_files,
    normalize_path,
    workspace_roots,
)
from codas.structure.loader import StructureMapError, load_structure_map
from codas.structure.models import StructureUnit

STRUCTURE_SOURCE = ".codas/structure.yml"
_MAX_CANDIDATES = 3


def check_missing_structure_owner(repo: Path, config: CodasConfig) -> list[Finding]:
    """Flag tracked artifacts that match no Structure Unit (missing_structure_owner).

    Initial Rule (schema §8): "Changed artifacts under governed paths match a unit
    with owner." The loader requires every unit to declare a non-empty owner, so
    "matches a unit with owner" reduces to "matches some unit"; the firing set is
    exactly ``build_artifact_index().unowned``. Status is ignored — a file under a
    planned/deprecated unit is still owned (active-boundary concerns belong to
    structure_drift). Whole working tree, deterministic, no diff, no LLM. Findings
    carry the artifact path plus the nearest candidate units as a remediation hint.
    """
    path = repo / ".codas" / "structure.yml"
    if not path.exists():
        return []  # absence is reported by config_sources

    try:
        structure_map = load_structure_map(path, source=STRUCTURE_SOURCE)
    except StructureMapError:
        return []  # malformedness is structure_map_loads' responsibility

    roots = workspace_roots(config.raw)
    files = discover_files(repo, roots)
    index = build_artifact_index(repo, roots, structure_map, files=files)

    findings: list[Finding] = []
    for artifact in index.unowned:
        candidates = nearest_candidate_units(artifact, structure_map.units)
        hint = f" (nearest: {', '.join(candidates)})" if candidates else ""
        findings.append(
            Finding(
                severity="error",
                check_id="missing-structure-owner",
                message=f"Artifact has no owning Structure Unit: {artifact}",
                evidence=[Evidence(path=artifact)],
                recommendation=f"Add a Structure Unit that owns this path{hint}.",
                meta={"nearest_candidates": candidates},
            )
        )

    findings.sort(key=lambda finding: finding.evidence[0].path)
    return findings


def nearest_candidate_units(
    artifact: str, units: tuple[StructureUnit, ...]
) -> list[str]:
    """Return up to three unit ids closest to ``artifact`` by shared leading path.

    Scores each unit by the count of matching leading path components against the
    artifact (glob unit paths compare on their literal head). Units sharing at
    least one component win; if none do, fall back to the whole set so the hint is
    never empty while units exist. Deterministic: sort by (-shared, unit_id).
    """
    art_parts = normalize_path(artifact).split("/")
    scored: list[tuple[int, str]] = []
    for unit in units:
        prefix = _literal_head(normalize_path(unit.path))
        shared = 0 if prefix == "" else _common_leading(art_parts, prefix.split("/"))
        scored.append((shared, unit.id))

    positive = [item for item in scored if item[0] > 0]
    pool = positive or scored
    pool.sort(key=lambda item: (-item[0], item[1]))
    return [unit_id for _shared, unit_id in pool[:_MAX_CANDIDATES]]


def _literal_head(prefix: str) -> str:
    """Leading glob-free portion of a unit path (``src/*/x`` -> ``src``)."""
    parts: list[str] = []
    for part in prefix.split("/"):
        if any(char in part for char in ("*", "?", "[")):
            break
        parts.append(part)
    return "/".join(parts)


def _common_leading(left: list[str], right: list[str]) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count
