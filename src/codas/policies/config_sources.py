from __future__ import annotations

from pathlib import Path

from codas.config.anchors import live_doc_anchor_files, unsupported_live_doc_patterns
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
    findings.extend(_check_anchor_live_documents(repo, config))
    return findings


def _check_anchor_live_documents(repo: Path, config: CodasConfig) -> list[Finding]:
    findings: list[Finding] = []
    files = tuple(
        path.relative_to(repo).as_posix()
        for path in repo.rglob("*")
        if path.is_file()
    )
    for pattern in unsupported_live_doc_patterns(config.anchor_live_documents):
        findings.append(
            Finding(
                severity="error",
                check_id="anchor-live-document-invalid",
                message=f"Configured live anchor document has unsupported extension: {pattern}",
                evidence=[
                    Evidence(
                        path=_rel(repo, config.path),
                        line=config.line_index.get(pattern),
                        detail=pattern,
                    )
                ],
                recommendation="Use .md or .html files for anchors.live_documents.",
                meta={"pattern": pattern},
            )
        )
    unsupported = set(unsupported_live_doc_patterns(config.anchor_live_documents))
    supported_patterns = tuple(
        pattern for pattern in config.anchor_live_documents if pattern not in unsupported
    )
    for pattern in supported_patterns:
        if live_doc_anchor_files(files, (pattern,)):
            continue
        findings.append(
            Finding(
                severity="error",
                check_id="anchor-live-document-missing",
                message=f"Configured live anchor document pattern matched no files: {pattern}",
                evidence=[
                    Evidence(
                        path=_rel(repo, config.path),
                        line=config.line_index.get(pattern),
                        detail=pattern,
                    )
                ],
                recommendation=(
                    "Update anchors.live_documents or add the declared live anchor document."
                ),
                meta={"pattern": pattern},
            )
        )
    return findings


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
