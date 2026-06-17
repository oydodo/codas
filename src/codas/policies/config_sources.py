from __future__ import annotations

from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding


def check_config_sources(repo: Path, config: CodasConfig) -> list[Finding]:
    findings: list[Finding] = []
    patterns = [
        ("authoritative", pattern)
        for pattern in config.authoritative_sources
    ] + [
        ("supporting", pattern)
        for pattern in config.supporting_sources
    ]
    for source_kind, pattern in patterns:
        matches = sorted(repo.glob(pattern))
        if matches:
            continue
        findings.append(
            Finding(
                severity="error" if source_kind == "authoritative" else "warning",
                check_id="declared-source-missing",
                message=f"Configured {source_kind} source pattern matched no files: {pattern}",
                evidence=[
                    Evidence(
                        path=_rel(repo, config.path),
                        line=config.line_index.get(pattern),
                        detail=pattern,
                    )
                ],
                recommendation="Update .codas/config.yml or add the declared source.",
                meta={"source_kind": source_kind, "pattern": pattern},
            )
        )
    return findings


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
