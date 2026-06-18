from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

VALID_STATUS = frozenset({"active", "planned", "deprecated", "removed", "external"})


@dataclass(frozen=True)
class StructureUnit:
    id: str
    path: str
    kind: str
    owner: str
    purpose: str
    canonical_placement: str
    status: str = "active"
    allowed_children: tuple[str, ...] = ()
    must_update_if_changed: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class DependencyRule:
    unit: str
    may_depend_on: tuple[str, ...] = ()
    must_not_depend_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeprecatedPath:
    id: str
    path: str
    status: str = ""
    replacement: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class StructureMap:
    version: int
    kind: str
    units: tuple[StructureUnit, ...]
    dependency_rules: tuple[DependencyRule, ...] = ()
    deprecated_paths: tuple[DeprecatedPath, ...] = ()
    source: str = ".codas/structure.yml"
    metadata: Mapping[str, object] = field(default_factory=dict)
    defaults: Mapping[str, object] = field(default_factory=dict)
    roles: Mapping[str, str] = field(default_factory=dict)

    def unit_ids(self) -> frozenset[str]:
        return frozenset(unit.id for unit in self.units)


@dataclass(frozen=True)
class WorkItem:
    id: str
    phase: str
    title: str
    status: str
    depends_on: tuple[str, ...] = ()
    trellis_tasks: tuple[str, ...] = ()
    theme: str = ""
    deliverables: tuple[str, ...] = ()
    exit_criteria: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgramPlan:
    version: int
    kind: str
    work_items: tuple[WorkItem, ...]
    source: str = ".codas/program.yml"
    metadata: Mapping[str, object] = field(default_factory=dict)
    defaults: Mapping[str, object] = field(default_factory=dict)

    def work_item_ids(self) -> frozenset[str]:
        return frozenset(item.id for item in self.work_items)
