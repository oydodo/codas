from __future__ import annotations

from pathlib import Path

from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.provenance import provenance_block
from codas.config.loader import load_codas_config, load_policies


def build_context_pack(repo: Path, task_id: str | None = None) -> dict:
    """Assemble the deterministic preflight Context Pack for a task.

    The read-first context Codas prepares for an agent before work (CONTEXT.md):
    the task, the authoritative sources to read, the dogfooding protocol, the active
    policies that will govern the work, and the C1 provenance pinning repo state.

    Adapter-free by design: task facts are read from the normalized inventory ``tasks``
    block, not the Trellis adapter — so ``codas-app`` honors its own
    ``must_not_depend_on: [codas-adapters]`` boundary. The inventory is built once and
    both the task facts and the ``inventory_hash`` derive from that single snapshot,
    so they can never disagree. Deterministic (sorted, content-hashed, no timestamp —
    timestamps live on the receipt).
    """
    config = load_codas_config(repo / ".codas" / "config.yml")
    inventory = run_inventory(repo)  # single snapshot for both task facts and the hash
    policies_raw = load_policies(repo / ".codas" / "policies.yml")

    task_items = inventory.get("tasks", {}).get("items", [])
    task = (
        next((item for item in task_items if item.get("id") == task_id), None)
        if task_id is not None
        else None
    )
    declared = policies_raw.get("policies", {}) or {}

    return {
        "schema_version": 1,
        "kind": "context_pack",
        "task": task,
        "available_tasks": sorted(
            item["id"] for item in task_items if item.get("id") is not None
        ),
        "read_first": sorted(config.authoritative_sources),
        "supporting": sorted(config.supporting_sources),
        "dogfooding_protocol": config.dogfooding_protocol,
        "policies": sorted(
            (
                {"id": pid, "severity": (body or {}).get("severity")}
                for pid, body in declared.items()
            ),
            key=lambda policy: policy["id"],
        ),
        # Same single inventory snapshot as the task facts above -> task and
        # inventory_hash can never disagree; provenance_block keeps the shape shared
        # with compute_provenance.
        "provenance": provenance_block(render_inventory_json(inventory), policies_raw),
    }
