from __future__ import annotations

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext
from codas.structure.index import GLOB_CHARS, normalize_path
from codas.structure.loader import StructureMapError, load_structure_map

STRUCTURE_SOURCE = ".codas/structure.yml"


def check_dependency_direction(ctx: ScanContext) -> list[Finding]:
    """Flag first-party imports that violate a Structure Map must_not_depend_on rule.

    Dogfooded enforcement of the §11 Adapter Boundary (and any declared dependency
    direction): an importer's most-specific owning unit must not import a unit listed
    in its ``must_not_depend_on``. Rules are local to the owning unit — schema-faithful,
    not inherited from ancestors. Consumes B1 import facts through the ScanContext
    seam, so the boundary-enforcing policy imports no adapter itself. Deterministic,
    no LLM (plan §17).
    """
    path = ctx.repo / ".codas" / "structure.yml"
    if not path.exists():
        return []  # absence is reported by config_sources
    try:
        structure_map = load_structure_map(path, source=STRUCTURE_SOURCE)
    except StructureMapError:
        return []  # malformedness is structure_map_loads' responsibility

    # Literal units only: a glob unit (e.g. .trellis/tasks/*) never owns a .py here.
    literal_units = [
        (normalize_path(unit.path), unit)
        for unit in structure_map.units
        if not any(char in normalize_path(unit.path) for char in GLOB_CHARS)
    ]
    unit_prefix = {unit.id: prefix for prefix, unit in literal_units}
    rules = {rule.unit: rule for rule in structure_map.dependency_rules}

    violations = []  # (importer_unit, forbidden_id, edge)
    targets_by_module: dict[str, set[str]] = {}
    for edge in ctx.imports().imports:
        if edge.target_path is None:
            continue  # external/stdlib import: no unit to govern
        importer = _owning_unit_of(edge.module, literal_units)
        target = _owning_unit_of(edge.target_path, literal_units)
        if importer is None or target is None:
            continue
        if importer.id == target.id:
            continue  # intra-unit import is never a violation
        rule = rules.get(importer.id)
        if rule is None:
            continue
        forbidden = _first_forbidden(edge.target_path, rule.must_not_depend_on, unit_prefix)
        if forbidden is None:
            continue
        violations.append((importer, forbidden, edge))
        targets_by_module.setdefault(edge.module, set()).add(edge.target)

    findings: list[Finding] = []
    for importer, forbidden, edge in violations:
        # A single `from pkg import sub` statement emits both the package and the
        # submodule edge. Collapse that redundancy by dropping any target that is a
        # strict dotted-ancestor of another violating target from the same importer,
        # keeping the most-specific leaf. Distinct submodules (pkg.a and pkg.b) do
        # not subsume each other, so genuinely separate imports stay separate.
        siblings = targets_by_module[edge.module]
        if any(other.startswith(edge.target + ".") for other in siblings):
            continue
        findings.append(
            Finding(
                severity="error",
                check_id="dependency-direction",
                message=(
                    f"Unit '{importer.id}' must not depend on '{forbidden}': "
                    f"{edge.module} imports {edge.target}"
                ),
                evidence=[
                    Evidence(path=edge.module, line=edge.line, detail=edge.target),
                    Evidence(path=edge.target_path),
                ],
                recommendation=(
                    f"Remove the import, or revise the '{importer.id}' "
                    "must_not_depend_on rule in the Structure Map."
                ),
                meta={
                    "importer_unit": importer.id,
                    "forbidden_unit": forbidden,
                    "target_path": edge.target_path,
                },
            )
        )

    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.meta["target_path"],
            finding.evidence[0].detail or "",
        )
    )
    return findings


def _owning_unit_of(path, literal_units):
    """Most-specific literal unit owning ``path`` (longest matching prefix wins)."""
    best = None
    best_len = -1
    for prefix, unit in literal_units:
        matches = prefix == "" or path == prefix or path.startswith(prefix + "/")
        if matches and len(prefix) > best_len:
            best_len = len(prefix)
            best = unit
    return best


def _first_forbidden(target_path, forbidden_ids, unit_prefix):
    """First forbidden unit id whose path prefix contains ``target_path`` (or None)."""
    for forbidden_id in sorted(forbidden_ids):
        prefix = unit_prefix.get(forbidden_id)
        if not prefix:  # unknown id, or root unit (would match everything) -> skip
            continue
        if target_path == prefix or target_path.startswith(prefix + "/"):
            return forbidden_id
    return None
