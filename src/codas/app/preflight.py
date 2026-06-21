from __future__ import annotations

from pathlib import Path

from codas.app.book import _read_chapter_prose
from codas.app.inventory import render_inventory_json, run_inventory
from codas.app.provenance import provenance_block
from codas.app.wiki import _owner_index, _owning
from codas.config.loader import load_codas_config, load_policies

# Cap on reuse-candidate symbols surfaced in the digest, so a task touching a large unit does
# not flood the session-start pack; a `truncated` flag + total keep the cut visible (no silent
# truncation). The full set is always queryable via `codas query symbols`.
_REUSE_CAP = 80


def _build_digest(repo: Path, inventory: dict, task: dict | None) -> dict | None:
    """The session-start DIGEST: reuse candidates + affected units + advisory why-prose, derived
    from the task's declared ``related_files`` (the path-level scope the coarse package/scope
    labels lack). ``None`` when no task is resolved; empty sections when the task declares no
    files. Deterministic (sorted, no timestamp); reuses the longest-prefix ownership helpers and
    the code-wiki prose reader rather than a second copy.

    The why-prose is host-authored, out-of-hash and ADVISORY — labelled so, and read by no gate
    (section 17): a between-sessions prose edit silently changes the pack, which is acceptable
    for an advisory hint and documented here.
    """
    if task is None:
        return None
    related = task.get("related_files") or []
    units = inventory.get("units") or []
    unit_by_id = {unit["id"]: unit for unit in units}
    owners = _owner_index(units)

    affected: dict[str, dict] = {}
    for path in related:
        unit_id, _owner = _owning(path, owners)
        if unit_id and unit_id in unit_by_id and unit_id not in affected:
            unit = unit_by_id[unit_id]
            affected[unit_id] = {
                "id": unit_id,
                "path": unit["path"],
                "owner": unit["owner"],
            }
    affected_units = sorted(affected.values(), key=lambda unit: unit["id"])

    # Reuse candidates: every top-level symbol defined under an affected unit's path — "these
    # already exist here," so the agent reuses before adding a duplicate the gate cannot catch
    # (duplicate_concept is planned). No inference of "what the task adds" (that would be
    # nondeterministic); the existing symbols ARE the deterministic signal.
    scope_paths = [unit["path"] for unit in affected_units if unit["path"] not in (".", "")]
    definitions = (inventory.get("symbols") or {}).get("definitions") or []
    candidates = sorted(
        (
            {
                "module": d["module"],
                "name": d["name"],
                "kind": d["kind"],
                "line": d["line"],
            }
            for d in definitions
            if any(
                d["module"] == prefix or d["module"].startswith(prefix + "/")
                for prefix in scope_paths
            )
        ),
        key=lambda c: (c["module"], c["line"], c["name"]),
    )

    advisory_why = {
        unit_id: prose
        for unit_id in sorted(affected)
        if (prose := _read_chapter_prose(repo, unit_id))
    }

    return {
        "affected_units": affected_units,
        "reuse_candidates": candidates[:_REUSE_CAP],
        "reuse_candidates_total": len(candidates),
        "reuse_candidates_truncated": len(candidates) > _REUSE_CAP,
        "advisory_why": advisory_why,
        "advisory_note": (
            "advisory: host-authored prose, out of the inventory hash; orienting context "
            "only, never a normative rule (section 17)."
        ),
    }


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
        # Session-start digest (reuse candidates + affected units + advisory why-prose),
        # derived from the resolved task's declared related_files; None when no task is given.
        "digest": _build_digest(repo, inventory, task),
        # Same single inventory snapshot as the task facts above -> task and
        # inventory_hash can never disagree; provenance_block keeps the shape shared
        # with compute_provenance.
        "provenance": provenance_block(render_inventory_json(inventory), policies_raw),
    }
