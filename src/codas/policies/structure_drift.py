from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.index import GLOB_CHARS, normalize_path
from codas.structure.loader import StructureMapError, load_structure_map

STRUCTURE_SOURCE = ".codas/structure.yml"


def check_structure_drift(repo: Path, config: CodasConfig) -> list[Finding]:
    """Flag active Structure Units whose declared path is absent (structure_drift).

    First Implementation facet (schema §8 / plan §10): the dual of artifact drift —
    the Structure Map declares an ``active`` boundary the working tree no longer
    satisfies. An active, literal (non-glob) unit whose path does not exist on disk
    is unmanaged drift (the path was deleted or moved without a map update). Needs
    no file scan: existence is ``(repo / prefix).exists()``, exactly how
    ``build_artifact_index`` computes ``observed.exists`` for literal prefixes.

    Exempt: non-active units (planned points at not-yet-created paths; deprecated /
    removed are ``deprecated_path_used``'s domain; external may point outside the
    repo), the root catch-all (empty prefix, always present), and glob paths
    (existence-as-match is a later facet). Whole-tree, deterministic, no LLM.
    """
    path = repo / ".codas" / "structure.yml"
    if not path.exists():
        return []  # absence is reported by config_sources

    try:
        structure_map = load_structure_map(path, source=STRUCTURE_SOURCE)
    except StructureMapError:
        return []  # malformedness is structure_map_loads' responsibility

    findings: list[Finding] = []
    for unit in structure_map.units:
        if unit.status != "active":
            continue
        prefix = normalize_path(unit.path)
        if prefix == "":
            continue  # root catch-all is always present
        if any(char in prefix for char in GLOB_CHARS):
            continue  # glob existence is a later facet
        if (repo / prefix).exists():
            continue
        findings.append(
            Finding(
                severity="error",
                check_id="structure-drift",
                message=(
                    f"Active Structure Unit '{unit.id}' declares a path that does "
                    f"not exist: {unit.path}"
                ),
                evidence=[Evidence(path=STRUCTURE_SOURCE, detail=f"units[{unit.id}]")],
                recommendation=(
                    "Restore the path, or update the unit (status or path) in the "
                    "Structure Map."
                ),
                meta={"unit": unit.id, "path": unit.path, "status": unit.status},
            )
        )

    findings.sort(key=lambda finding: finding.meta["unit"])
    return findings
