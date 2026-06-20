from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.app.inventory import run_inventory

# ``codas query`` / ``codas schema`` — the jq-optional half of the P7 CLI-first agent
# query surface (sibling to ``codas impact``). Pure projection over the deterministic
# inventory: ``query`` returns one fact block's rows (optionally field-filtered),
# ``schema`` returns the row shape derived from the live inventory. Read-only, no new
# extraction, no adapter import (projects ``codas inventory``).

# kind -> (inventory block, row-list subkey or None when the block IS the list).
_KINDS: dict[str, tuple[str, str | None]] = {
    "symbols": ("symbols", "definitions"),
    "imports": ("imports", "edges"),
    "calls": ("calls", "edges"),
    "units": ("units", None),
    "tasks": ("tasks", "items"),
    "doc-claims": ("doc_claims", "references"),
    "html-claims": ("html_claims", "references"),
    "wiki-claims": ("wiki_claims", "claims"),
    "work-items": ("program", "work_items"),
}


def kinds() -> list[str]:
    """The valid ``query`` kinds, sorted (for help text + error messages)."""
    return sorted(_KINDS)


class QueryError(ValueError):
    """An invalid query (unknown kind / malformed selector). Carries an exit-2 message."""


def _rows_for(inventory: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    block_name, subkey = _KINDS[kind]
    block = inventory.get(block_name)
    if block is None:
        return []
    if subkey is None:
        return list(block) if isinstance(block, list) else []
    rows = block.get(subkey, []) if isinstance(block, dict) else []
    return list(rows)


def parse_selectors(raw: list[str]) -> list[tuple[str, str]]:
    """Parse ``FIELD=VALUE`` selectors. Splits on the first ``=`` only (so a value may
    contain ``=``). A selector without ``=`` is a QueryError."""
    out: list[tuple[str, str]] = []
    for item in raw:
        field, sep, value = item.partition("=")
        if not sep or not field:
            raise QueryError(f"malformed --select {item!r}: expected FIELD=VALUE")
        out.append((field, value))
    return out


def _scalar_str(value: Any) -> str:
    """Render a row scalar the way it appears in the JSON output, so a selector value a
    user copies from `codas query`/`schema` output matches: a bool is ``true``/``false``
    (not Python ``True``), ``None`` is ``null``. (``bool`` is checked before the ``str``
    fallback because ``bool`` is an ``int`` subclass.)"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _row_matches(row: dict[str, Any], selectors: list[tuple[str, str]]) -> bool:
    # JSON-spelled comparison so numeric (line) and bool/null fields filter as the output
    # shows them; a row missing the field never matches (so an unknown field yields an
    # empty result, not an error).
    for field, value in selectors:
        if field not in row or _scalar_str(row[field]) != value:
            return False
    return True


def run_query(repo: Path, kind: str, selectors: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Rows of one inventory fact block, optionally filtered by FIELD=VALUE (AND).

    Deterministic: the inventory rows are already adapter-sorted and the filter preserves
    that order. Read-only — builds the same inventory ``codas inventory`` does.
    """
    if kind not in _KINDS:
        raise QueryError(
            f"unknown query kind {kind!r}; valid kinds: {', '.join(kinds())}"
        )
    rows = _rows_for(run_inventory(repo), kind)
    if not selectors:
        return rows
    return [row for row in rows if _row_matches(row, selectors)]


def run_schema(repo: Path) -> dict[str, Any]:
    """The row shape per kind, derived from the live inventory (no hand-authored drift).

    For each kind: the backing inventory ``block``/``rows`` key and the sorted union of
    field names across that block's rows. A populated repo yields the complete field set;
    an empty block yields ``fields: []`` (honest about what is present).
    """
    inventory = run_inventory(repo)
    schema: dict[str, Any] = {}
    for kind in kinds():
        block_name, subkey = _KINDS[kind]
        rows = _rows_for(inventory, kind)
        fields: set[str] = set()
        for row in rows:
            if isinstance(row, dict):
                fields.update(row.keys())
        schema[kind] = {
            "block": block_name,
            "rows": subkey,
            "count": len(rows),
            "fields": sorted(fields),
        }
    return schema
