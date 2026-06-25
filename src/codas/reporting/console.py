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
        repair_target = finding.meta.get("repair_target")
        if isinstance(repair_target, dict):
            old_node = _node_value(repair_target.get("old_node"))
            best_node = _node_value(repair_target.get("best_match_new_node"))
            action = repair_target.get("action")
            if old_node:
                suffix = f" -> likely {best_node}" if best_node else " -> no deterministic match"
                print(f"  RepairTarget: {old_node}{suffix} ({action})")
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

    digest = pack.get("digest")
    if digest:
        _print_digest(digest)

    repair_targets = pack.get("repair_targets") or []
    if repair_targets:
        print("Repair targets:")
        for target in repair_targets:
            best = target.get("best_match_new_node") or "no deterministic match"
            print(
                f"  - {target['source']}:{target['line']} "
                f"{target['old_node']} -> {best} ({target['action']})"
            )

    hints = pack.get("advisory_reuse_hints") or []
    if hints:
        print("CodeGraph advisory reuse hints:")
        for hint in hints:
            caller = _hint_fqn(hint, "caller")
            callee = _hint_fqn(hint, "callee")
            print(
                f"  - {caller} -> {callee} "
                f"({hint['callee_path']}:{hint['callee_line']}, "
                f"provenance={hint['provenance']}, resolution={hint['resolution']})"
            )


def _node_value(value: object) -> str | None:
    if isinstance(value, dict):
        raw = value.get("value")
        return raw if isinstance(raw, str) else None
    return None


def _hint_fqn(hint: dict, prefix: str) -> str:
    parts = [str(hint.get(f"{prefix}_module") or "")]
    cls = hint.get(f"{prefix}_class")
    if cls:
        parts.append(str(cls))
    parts.append(str(hint.get(f"{prefix}_symbol") or ""))
    return ".".join(part for part in parts if part)


def _print_digest(digest: dict) -> None:
    """Render the session-start digest (affected units + reuse candidates + advisory why)."""
    units = digest.get("affected_units") or []
    if units:
        print("Affected units:")
        for unit in units:
            print(f"  - {unit['id']} ({unit['path']}) — {unit['owner']}")

    candidates = digest.get("reuse_candidates") or []
    if candidates:
        total = digest.get("reuse_candidates_total", len(candidates))
        suffix = (
            f" (showing {len(candidates)}/{total}; `codas query symbols` for all)"
            if digest.get("reuse_candidates_truncated")
            else ""
        )
        print(f"Reuse candidates — exist here, reuse before adding{suffix}:")
        for candidate in candidates:
            print(
                f"  - {candidate['name']} ({candidate['kind']}) "
                f"{candidate['module']}:{candidate['line']}"
            )

    advisory = digest.get("advisory_why") or {}
    if advisory:
        print(f"Advisory why ({digest.get('advisory_note', '')}):")
        for unit_id, prose in advisory.items():
            first_line = prose.splitlines()[0] if prose else ""
            print(f"  - {unit_id}: {first_line}")
