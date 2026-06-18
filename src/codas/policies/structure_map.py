from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.loader import StructureMapError, load_structure_map

STRUCTURE_SOURCE = ".codas/structure.yml"


def check_structure_map(repo: Path, config: CodasConfig) -> list[Finding]:
    """Verify the Structure Map loads and is well-formed (structure_map_loads).

    Reference-integrity failures (dangling allowed_children, unknown dependency
    targets, missing required fields) surface here too, since they make the map
    malformed.
    """
    path = repo / ".codas" / "structure.yml"
    if not path.exists():
        return []

    try:
        load_structure_map(path, source=STRUCTURE_SOURCE)
    except StructureMapError as error:
        return [
            Finding(
                severity="error",
                check_id="structure-map-loads",
                message=str(error),
                evidence=[Evidence(path=STRUCTURE_SOURCE)],
                recommendation="Fix the Structure Map so it parses and resolves all unit references.",
            )
        ]
    return []
