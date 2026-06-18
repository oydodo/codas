from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from codas.config.loader import CodasConfig


@dataclass(frozen=True)
class TaskFact:
    id: str
    status: str
    package: str | None
    dev_type: str | None
    priority: str | None
    archived: bool


@dataclass(frozen=True)
class TaskFacts:
    items: tuple[TaskFact, ...]
    skipped: tuple[str, ...]
    source_root: str


def extract_task_facts(repo: Path, config: CodasConfig) -> TaskFacts:
    """Read Trellis task.json records (active + archived) into task facts.

    Malformed task.json is recorded in `skipped` rather than raising, so a stray
    file never hard-fails the inventory but stays visible.
    """
    tasks_root = repo / (config.workflow_root or ".trellis") / "tasks"
    source_root = tasks_root.relative_to(repo).as_posix()
    if not tasks_root.exists():
        return TaskFacts((), (), source_root)

    items: list[TaskFact] = []
    skipped: list[str] = []
    for task_json in sorted(tasks_root.glob("**/task.json")):
        rel = task_json.relative_to(repo).as_posix()
        try:
            data = json.loads(task_json.read_text(errors="ignore"))
        except (json.JSONDecodeError, OSError, ValueError):
            skipped.append(rel)
            continue
        if not isinstance(data, dict):
            skipped.append(rel)
            continue

        archived = "archive" in task_json.relative_to(tasks_root).parts
        task_id = data.get("id") or data.get("name") or task_json.parent.name
        items.append(
            TaskFact(
                id=str(task_id),
                status=str(data.get("status") or ""),
                package=_optional_str(data.get("package")),
                dev_type=_optional_str(data.get("dev_type")),
                priority=_optional_str(data.get("priority")),
                archived=archived,
            )
        )

    items.sort(key=lambda task: (task.archived, task.id))
    return TaskFacts(tuple(items), tuple(sorted(skipped)), source_root)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
