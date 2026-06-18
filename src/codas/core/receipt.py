from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Receipt:
    """A durable record of a Codas run (CONTEXT.md Receipt).

    Captures the inputs, the provenance hashes that pin which inventory facts and
    policy config the run saw (P4 C1), the findings and the pass/fail result. A pure
    value — no I/O; the app layer writes it to ``.codas/receipts/``.
    """

    timestamp: str  # ISO-8601 UTC, e.g. 2026-06-18T12:00:00Z
    repo: str
    provenance: dict[str, str | None]
    ok: bool
    error_count: int
    warning_count: int
    findings: list[dict] = field(default_factory=list)

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "receipt",
            "timestamp": self.timestamp,
            # Absolute path: a receipt records *this* local/CI run, not a portable
            # artifact. In shared CI artifacts this exposes the build machine path.
            "repo": self.repo,
            "provenance": self.provenance,
            "result": {
                "ok": self.ok,
                "error_count": self.error_count,
                "warning_count": self.warning_count,
            },
            "findings": self.findings,
        }
