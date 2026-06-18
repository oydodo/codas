from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from codas.app.inventory import render_inventory_json, run_inventory
from codas.config.loader import load_policies
from codas.core.provenance import inventory_hash, policy_version

T = TypeVar("T")


def compute_provenance(repo: Path) -> dict[str, str | None]:
    """Provenance block for a run: pins the inventory facts and policy config.

    Scope: ``inventory + declared policy config``. It records *which facts* and
    *which policy declarations* a run saw — not the fully-effective check inputs,
    since ``waivers.yml`` (which suppresses findings) is out of scope for now. The
    receipt (P4 C2) adds run identity (timestamp/task) on top of these hashes.

    Orchestration only: it runs the inventory engine and loads the policy config,
    then delegates the hashing to the pure ``core.provenance`` primitives — so the
    dependency direction stays downward (app -> core, never core -> app).

    Best-effort: each hash is computed independently and degrades to ``None`` if its
    input is missing or malformed. Provenance is metadata for a ``check`` run, so a
    broken ``policies.yml``/``structure.yml`` must not abort the report (``run_check``
    already surfaces that as a load-error finding).
    """
    inventory_json = _safe(lambda: render_inventory_json(run_inventory(repo)))
    policies = _safe(lambda: load_policies(repo / ".codas" / "policies.yml"))
    return provenance_block(inventory_json, policies)


def provenance_block(inventory_json: str | None, policies_raw: dict | None) -> dict[str, str | None]:
    """Build the provenance dict from already-loaded inputs (the single shape).

    Shared by ``compute_provenance`` (best-effort, may pass ``None`` inputs) and the
    preflight context pack (which passes its own single inventory snapshot), so the
    two cannot drift in shape or hashing.
    """
    return {
        "inventory_hash": inventory_hash(inventory_json) if inventory_json is not None else None,
        "policy_version": policy_version(policies_raw) if policies_raw is not None else None,
    }


def _safe(compute: Callable[[], T]) -> T | None:
    try:
        return compute()
    except Exception:  # best-effort metadata: any load/parse failure -> None
        return None
