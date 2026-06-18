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


def print_context_pack(pack: dict) -> None:
    """Human summary of a preflight Context Pack."""
    task = pack.get("task")
    print(f"Task: {task['id']} ({task['status']})" if task else "Task: (none)")

    provenance = pack.get("provenance", {})
    print(f"Inventory: {provenance.get('inventory_hash')}")
    print(f"Policies:  {provenance.get('policy_version')}")

    print("Read first:")
    for source in pack.get("read_first", []):
        print(f"  - {source}")
    if pack.get("dogfooding_protocol"):
        print(f"  - {pack['dogfooding_protocol']}")

    print(f"Active policies: {len(pack.get('policies', []))}")
    for policy in pack.get("policies", []):
        print(f"  - {policy['id']} ({policy['severity']})")
