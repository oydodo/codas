from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding


REQUIRED_TASK_FILES = ("task.json", "prd.md", "implement.jsonl", "check.jsonl")


def check_trellis_context(repo: Path, config: CodasConfig) -> list[Finding]:
    findings: list[Finding] = []
    if config.workflow_adapter != "trellis":
        return findings

    required_patterns = {
        "implement.jsonl": "implement.jsonl",
        "check.jsonl": "check.jsonl",
    }
    for label, needle in required_patterns.items():
        if any(needle in pattern for pattern in config.workflow_task_globs):
            continue
        findings.append(
            Finding(
                severity="error",
                check_id="trellis-task-glob-missing",
                message=f"Trellis task_globs do not include {label}.",
                evidence=[Evidence(path=_rel(repo, config.path), detail="workflow.task_globs")],
                recommendation=f"Add active and archived {label} globs to .codas/config.yml.",
                meta={"missing": label},
            )
        )

    trellis_root = repo / (config.workflow_root or ".trellis")
    tasks_root = trellis_root / "tasks"
    if not tasks_root.exists():
        findings.append(
            Finding(
                severity="error",
                check_id="trellis-tasks-root-missing",
                message=f"Trellis tasks root does not exist: {_rel(repo, tasks_root)}",
                evidence=[Evidence(path=_rel(repo, config.path), detail="workflow.root")],
            )
        )
        return findings

    for task_json in sorted(tasks_root.glob("**/task.json")):
        task_dir = task_json.parent
        for filename in REQUIRED_TASK_FILES:
            expected = task_dir / filename
            if expected.exists():
                continue
            findings.append(
                Finding(
                    severity="warning",
                    check_id="trellis-task-context-missing",
                    message=f"Trellis task is missing {filename}: {_rel(repo, task_dir)}",
                    evidence=[Evidence(path=_rel(repo, task_json))],
                    recommendation="Initialize or repair the Trellis task context before implementation.",
                    meta={"task": _rel(repo, task_dir), "missing_file": filename},
                )
            )
    return findings


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
