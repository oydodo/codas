from __future__ import annotations

import hashlib
import json


def digest(text: str) -> str:
    """Content digest of ``text`` as ``sha256:<hex>`` (stable, stdlib only)."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def inventory_hash(inventory_json: str) -> str:
    """Provenance hash pinning the inventory facts a run observed.

    Hashes the canonical inventory artifact (the byte-identical
    ``render_inventory_json`` output) so the hash is robust to internal refactors —
    same facts produce the same hash.
    """
    return digest(inventory_json)


def policy_version(policies_raw: dict) -> str:
    """Provenance hash pinning the declared policy configuration a run ran.

    Canonical ``json.dumps(sort_keys=True)`` so YAML key order never affects the
    hash. ``default=str`` coerces any non-JSON raw value (e.g. a YAML date)
    deterministically rather than failing.
    """
    canonical = json.dumps(
        policies_raw, sort_keys=True, separators=(",", ":"), default=str
    )
    return digest(canonical)
