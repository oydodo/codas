from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.config.loader import ConfigLoadError, load_yaml_mapping

from .models import (
    VALID_STATUS,
    DependencyRule,
    DeprecatedPath,
    StructureMap,
    StructureUnit,
)

REQUIRED_UNIT_FIELDS = ("path", "kind", "owner", "purpose", "canonical_placement")


class StructureMapError(RuntimeError):
    """Raised when the Structure Map cannot be loaded or is malformed.

    Maps to the schema `structure_map_loads` policy.
    """

    def __init__(self, message: str, source: str) -> None:
        super().__init__(message)
        self.source = source


def load_structure_map(path: Path, source: str | None = None) -> StructureMap:
    src = source or path.name

    try:
        raw = load_yaml_mapping(path)
    except ConfigLoadError as error:
        raise StructureMapError(str(error), src) from error

    version = raw.get("version")
    if not isinstance(version, int):
        raise StructureMapError("structure map missing integer 'version'", src)
    kind = raw.get("kind")
    if kind != "structure_map":
        raise StructureMapError(
            f"structure map 'kind' must be 'structure_map', got {kind!r}", src
        )
    units_raw = raw.get("units")
    if not isinstance(units_raw, dict) or not units_raw:
        raise StructureMapError("structure map has no 'units' mapping", src)

    defaults = _mapping(raw.get("defaults"))
    default_status = defaults.get("status", "active")

    units: list[StructureUnit] = []
    for unit_id, body in units_raw.items():
        if not isinstance(body, dict):
            raise StructureMapError(f"unit {unit_id!r} is not a mapping", src)
        for field_name in REQUIRED_UNIT_FIELDS:
            value = body.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise StructureMapError(
                    f"unit {unit_id!r} missing required field {field_name!r}", src
                )
        status = body.get("status", default_status)
        if status not in VALID_STATUS:
            raise StructureMapError(
                f"unit {unit_id!r} has invalid status {status!r}", src
            )
        units.append(
            StructureUnit(
                id=str(unit_id),
                path=body["path"],
                kind=body["kind"],
                owner=body["owner"],
                purpose=body["purpose"],
                canonical_placement=body["canonical_placement"],
                status=str(status),
                allowed_children=_str_tuple(body.get("allowed_children")),
                must_update_if_changed=_str_tuple(body.get("must_update_if_changed")),
                evidence=_str_tuple(body.get("evidence")),
            )
        )

    unit_ids = {unit.id for unit in units}

    for unit in units:
        for child in unit.allowed_children:
            if child not in unit_ids:
                raise StructureMapError(
                    f"unit {unit.id!r} allowed_children references unknown unit {child!r}",
                    src,
                )

    dependency_rules = _load_dependency_rules(raw.get("dependency_rules"), unit_ids, src)
    deprecated_paths = _load_deprecated_paths(raw.get("deprecated_paths"), src)

    roles = {str(k): str(v) for k, v in _mapping(raw.get("roles")).items()}

    return StructureMap(
        version=version,
        kind=kind,
        units=tuple(units),
        dependency_rules=dependency_rules,
        deprecated_paths=deprecated_paths,
        source=src,
        metadata=_mapping(raw.get("metadata")),
        defaults=defaults,
        roles=roles,
    )


def _load_dependency_rules(
    raw: Any, unit_ids: set[str], src: str
) -> tuple[DependencyRule, ...]:
    rules: list[DependencyRule] = []
    for rule_unit, body in _mapping(raw).items():
        if rule_unit not in unit_ids:
            raise StructureMapError(
                f"dependency_rules references unknown unit {rule_unit!r}", src
            )
        body = body if isinstance(body, dict) else {}
        may = _str_tuple(body.get("may_depend_on"))
        must_not = _str_tuple(body.get("must_not_depend_on"))
        for target in (*may, *must_not):
            if target not in unit_ids:
                raise StructureMapError(
                    f"dependency_rules[{rule_unit!r}] references unknown unit {target!r}",
                    src,
                )
        rules.append(
            DependencyRule(
                unit=str(rule_unit), may_depend_on=may, must_not_depend_on=must_not
            )
        )
    return tuple(rules)


def _load_deprecated_paths(raw: Any, src: str) -> tuple[DeprecatedPath, ...]:
    paths: list[DeprecatedPath] = []
    for dep_id, body in _mapping(raw).items():
        body = body if isinstance(body, dict) else {}
        dep_path = body.get("path")
        if not isinstance(dep_path, str) or not dep_path.strip():
            raise StructureMapError(
                f"deprecated_paths[{dep_id!r}] missing 'path'", src
            )
        paths.append(
            DeprecatedPath(
                id=str(dep_id),
                path=dep_path,
                status=str(body.get("status", "")),
                replacement=_optional_str(body.get("replacement")),
                reason=_optional_str(body.get("reason")),
            )
        )
    return tuple(paths)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if item is not None)
    return ()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
