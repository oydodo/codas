from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    path: str
    line: int | None = None
    detail: str | None = None

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = {"path": self.path}
        if self.line is not None:
            payload["line"] = self.line
        if self.detail:
            payload["detail"] = self.detail
        return payload


@dataclass(frozen=True)
class Finding:
    severity: str
    check_id: str
    message: str
    evidence: list[Evidence] = field(default_factory=list)
    recommendation: str | None = None
    meta: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "severity": self.severity,
            "check_id": self.check_id,
            "message": self.message,
            "evidence": [evidence.to_json() for evidence in self.evidence],
        }
        if self.recommendation:
            payload["recommendation"] = self.recommendation
        if self.meta:
            payload["meta"] = self.meta
        return payload


@dataclass(frozen=True)
class CheckReport:
    repo: str
    findings: list[Finding]

    @property
    def has_errors(self) -> bool:
        return any(finding.severity == "error" for finding in self.findings)

    def to_json(self) -> dict[str, object]:
        return {
            "repo": self.repo,
            "ok": not self.has_errors,
            "findings": [finding.to_json() for finding in self.findings],
        }
