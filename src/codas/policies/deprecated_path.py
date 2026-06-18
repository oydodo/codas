from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.index import discover_files, normalize_path, workspace_roots
from codas.structure.loader import StructureMapError, load_structure_map

STRUCTURE_SOURCE = ".codas/structure.yml"


def check_deprecated_path_used(repo: Path, config: CodasConfig) -> list[Finding]:
    """Flag tracked artifacts that live under a deprecated/removed Structure path.

    Initial Rule (schema §8): "New files must not be added under deprecated or
    removed paths." This slice enforces a deliberate, stricter whole-tree superset
    (any existing file under a deprecated prefix), since diff scoping is a later
    expansion. Both ``deprecated`` and ``removed`` statuses fire — §8 names both;
    ``status`` is descriptive only. Literal prefixes only (glob deferred). The
    replacement path is surfaced when the Structure Map declares one.
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

    # (prefix, dep) for every non-empty deprecated path. An empty/'.' prefix would
    # match the whole repo: skip it as misconfiguration rather than flag every file.
    candidates = [
        (normalize_path(dep.path), dep) for dep in structure_map.deprecated_paths
    ]
    candidates = [(prefix, dep) for prefix, dep in candidates if prefix != ""]

    findings: list[Finding] = []
    for artifact in files:
        matches = [
            (prefix, dep)
            for prefix, dep in candidates
            if artifact == prefix or artifact.startswith(prefix + "/")
        ]
        if not matches:
            continue
        # Overlapping deprecated prefixes can both match one file; report it once
        # under the most-specific (longest) prefix, tie-broken by id for determinism.
        prefix, dep = max(matches, key=lambda pair: (len(pair[0]), pair[1].id))
        recommendation = (
            f"Move it under {dep.replacement}."
            if dep.replacement
            else "Move it out of the deprecated path."
        )
        if dep.reason:
            recommendation += f" ({dep.reason})"
        findings.append(
            Finding(
                severity="error",
                check_id="deprecated-path-used",
                message=(
                    f"Artifact lives under a {dep.status or 'deprecated'} "
                    f"path: {artifact}"
                ),
                evidence=[
                    Evidence(path=artifact, detail=dep.path),
                    Evidence(path=STRUCTURE_SOURCE, detail=f"deprecated_paths[{dep.id}]"),
                ],
                recommendation=recommendation,
                meta={
                    "deprecated_path": dep.path,
                    "status": dep.status,
                    "replacement": dep.replacement,
                },
            )
        )

    # One finding per artifact, so the artifact path is already a total sort key.
    findings.sort(key=lambda finding: finding.evidence[0].path)
    return findings
