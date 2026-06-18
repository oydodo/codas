from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.program_loader import ProgramPlanError, load_program_plan

PROGRAM_SOURCE = ".codas/program.yml"


def check_program_plan(repo: Path, config: CodasConfig) -> list[Finding]:
    """Verify the Program Plan loads and is well-formed (program_plan_loads).

    Catches malformed work items, bad ids, dangling depends_on and dependency
    cycles before they surface at `codas inventory` time. A missing program.yml
    is handled by check_config_sources (it is a declared authoritative source).
    """
    path = repo / ".codas" / "program.yml"
    if not path.exists():
        return []

    try:
        load_program_plan(path, source=PROGRAM_SOURCE)
    except ProgramPlanError as error:
        return [
            Finding(
                severity="error",
                check_id="program-plan-loads",
                message=str(error),
                evidence=[Evidence(path=PROGRAM_SOURCE)],
                recommendation="Fix the Program Plan so it parses and resolves all work-item references.",
            )
        ]
    return []
