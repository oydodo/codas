from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from codas.core.models import Evidence, Finding


def check_waivers(repo: Path, path: Path, waivers_doc: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    waivers = waivers_doc.get("waivers", [])
    if not isinstance(waivers, list):
        return [
            Finding(
                severity="error",
                check_id="waiver-schema-invalid",
                message="waivers must be a list.",
                evidence=[Evidence(path=_rel(repo, path))],
            )
        ]

    for index, waiver in enumerate(waivers, start=1):
        if not isinstance(waiver, dict):
            findings.append(_invalid(path, repo, index, "waiver entry must be a mapping"))
            continue
        for key in ("id", "reason", "owner", "expires"):
            if waiver.get(key):
                continue
            findings.append(_invalid(path, repo, index, f"waiver is missing {key}"))
        expires = waiver.get("expires")
        if isinstance(expires, str):
            try:
                expiry = date.fromisoformat(expires)
            except ValueError:
                findings.append(_invalid(path, repo, index, "waiver expires must be YYYY-MM-DD"))
            else:
                if expiry < date.today():
                    findings.append(_invalid(path, repo, index, "waiver has expired"))
    return findings


def _invalid(path: Path, repo: Path, index: int, message: str) -> Finding:
    return Finding(
        severity="error",
        check_id="waiver-schema-invalid",
        message=message,
        evidence=[Evidence(path=_rel(repo, path), detail=f"waivers[{index}]")],
        recommendation="Fix .codas/waivers.yml or remove the invalid waiver.",
    )


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
