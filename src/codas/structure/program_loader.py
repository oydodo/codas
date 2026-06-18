from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from codas.config.loader import ConfigLoadError, load_yaml_mapping

from .models import ProgramPlan, WorkItem

WORK_ITEM_ID = re.compile(r"^program:P\d+:[a-z0-9-]+$")
REQUIRED_ITEM_FIELDS = ("phase", "title")


class ProgramPlanError(RuntimeError):
    """Raised when the Program Plan cannot be loaded or is malformed."""

    def __init__(self, message: str, source: str) -> None:
        super().__init__(message)
        self.source = source


def load_program_plan(path: Path, source: str | None = None) -> ProgramPlan:
    src = source or path.name

    try:
        raw = load_yaml_mapping(path)
    except ConfigLoadError as error:
        raise ProgramPlanError(str(error), src) from error

    version = raw.get("version")
    if not isinstance(version, int):
        raise ProgramPlanError("program plan missing integer 'version'", src)
    kind = raw.get("kind")
    if kind != "program_plan":
        raise ProgramPlanError(
            f"program plan 'kind' must be 'program_plan', got {kind!r}", src
        )
    items_raw = raw.get("work_items")
    if not isinstance(items_raw, list) or not items_raw:
        raise ProgramPlanError("program plan has no 'work_items' list", src)

    defaults = _mapping(raw.get("defaults"))
    default_status = defaults.get("status")

    items: list[WorkItem] = []
    for entry in items_raw:
        if not isinstance(entry, dict):
            raise ProgramPlanError("work_item is not a mapping", src)
        work_id = entry.get("id")
        if not isinstance(work_id, str) or not WORK_ITEM_ID.match(work_id):
            raise ProgramPlanError(f"work_item has invalid id {work_id!r}", src)
        for field_name in REQUIRED_ITEM_FIELDS:
            value = entry.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ProgramPlanError(
                    f"work_item {work_id!r} missing required field {field_name!r}", src
                )
        status = entry.get("status", default_status)
        if not isinstance(status, str) or not status.strip():
            raise ProgramPlanError(
                f"work_item {work_id!r} missing 'status' (no item value or defaults.status)",
                src,
            )
        items.append(
            WorkItem(
                id=work_id,
                phase=entry["phase"],
                title=entry["title"],
                status=status,
                depends_on=_str_tuple(entry.get("depends_on")),
                trellis_tasks=_str_tuple(entry.get("trellis_tasks")),
                theme=str(entry.get("theme", "")),
                deliverables=_str_tuple(entry.get("deliverables")),
                exit_criteria=_str_tuple(entry.get("exit_criteria")),
            )
        )

    ids = {item.id for item in items}
    if len(ids) != len(items):
        raise ProgramPlanError("duplicate work_item id", src)
    for item in items:
        for dep in item.depends_on:
            if dep not in ids:
                raise ProgramPlanError(
                    f"work_item {item.id!r} depends_on unknown id {dep!r}", src
                )

    _assert_acyclic(items, src)

    return ProgramPlan(
        version=version,
        kind=kind,
        work_items=tuple(items),
        source=src,
        metadata=_mapping(raw.get("metadata")),
        defaults=_mapping(raw.get("defaults")),
    )


def _assert_acyclic(items: list[WorkItem], src: str) -> None:
    """Iterative DFS cycle check (no recursion-depth limit on long chains).

    GRAY = on the current path, BLACK = fully explored. A GRAY neighbour is a
    back edge (cycle); a BLACK neighbour (e.g. a diamond's shared dependency) is
    already done and skipped.
    """
    graph = {item.id: item.depends_on for item in items}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    for start in graph:
        if color[start] != WHITE:
            continue
        color[start] = GRAY
        stack: list[tuple[str, list[str]]] = [(start, list(graph[start]))]
        while stack:
            node, pending = stack[-1]
            advanced = False
            while pending:
                dep = pending.pop()
                if color[dep] == GRAY:
                    raise ProgramPlanError(
                        f"dependency cycle through {dep!r}", src
                    )
                if color[dep] == WHITE:
                    color[dep] = GRAY
                    stack.append((dep, list(graph[dep])))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if item is not None)
    return ()
