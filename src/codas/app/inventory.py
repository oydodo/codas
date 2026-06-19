from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from codas.structure.inventory import build_inventory

if TYPE_CHECKING:
    from codas.facts.context import ScanContext


def run_inventory(
    repo: Path,
    exclude_under: tuple[str, ...] = (),
    ctx: "ScanContext | None" = None,
) -> dict[str, Any]:
    return build_inventory(repo, exclude_under=exclude_under, ctx=ctx)


def render_inventory_json(inventory: dict[str, Any]) -> str:
    return json.dumps(inventory, indent=2, sort_keys=True)


def render_inventory_summary(inventory: dict[str, Any]) -> str:
    units = inventory.get("units", [])
    missing = [unit["id"] for unit in units if not unit["observed"]["exists"]]
    unowned = inventory.get("unowned", [])
    program = inventory.get("program", {})
    work_items = program.get("work_items", [])

    phase_counts: dict[str, int] = {}
    for item in work_items:
        status = item.get("status", "unknown")
        phase_counts[status] = phase_counts.get(status, 0) + 1

    lines = [
        f"Atlas inventory for {inventory.get('source', '?')}",
        f"  units: {len(units)} ({len(missing)} not on disk)",
        f"  unowned artifacts: {len(unowned)}",
    ]
    if work_items:
        breakdown = ", ".join(f"{status}={count}" for status, count in sorted(phase_counts.items()))
        lines.append(f"  program work_items: {len(work_items)} ({breakdown})")
    if missing:
        lines.append(f"  not on disk: {', '.join(missing)}")
    if unowned:
        preview = ", ".join(unowned[:5])
        suffix = "" if len(unowned) <= 5 else f", +{len(unowned) - 5} more"
        lines.append(f"  unowned: {preview}{suffix}")
    return "\n".join(lines)
