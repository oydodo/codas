from __future__ import annotations

from codas.core.models import Finding


def print_findings(findings: list[Finding]) -> None:
    if not findings:
        print("No Codas findings.")
        return

    order = {"error": 0, "warning": 1, "info": 2}
    for finding in sorted(findings, key=lambda item: (order.get(item.severity, 99), item.check_id)):
        print(f"[{finding.severity.upper()}] {finding.check_id}")
        print(f"  {finding.message}")
        for evidence in finding.evidence:
            location = evidence.path
            if evidence.line is not None:
                location = f"{location}:{evidence.line}"
            if evidence.detail:
                print(f"  Evidence: {location} ({evidence.detail})")
            else:
                print(f"  Evidence: {location}")
        if finding.recommendation:
            print(f"  Fix: {finding.recommendation}")
        print()
