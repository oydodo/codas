from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from codas.app.provenance import compute_provenance
from codas.core.models import CheckReport
from codas.core.receipt import Receipt

_MAX_RECEIPTS_PER_SECOND = 1000


def build_receipt(
    repo: Path, report: CheckReport, provenance: dict[str, str | None], now: datetime
) -> Receipt:
    """Assemble a Receipt from a check report + provenance + a timestamp (pure)."""
    return Receipt(
        timestamp=_iso(now),
        repo=repo.as_posix(),
        provenance=dict(provenance),  # snapshot: later mutation must not alter the receipt
        ok=not report.has_errors,
        error_count=sum(1 for f in report.findings if f.severity == "error"),
        warning_count=sum(1 for f in report.findings if f.severity == "warning"),
        findings=[finding.to_json() for finding in report.findings],
    )


def write_receipt(repo: Path, report: CheckReport, now: datetime | None = None) -> Path:
    """Write a durable receipt of a run to ``.codas/receipts/<timestamp>.json``.

    Append-only: a same-second second receipt gets a ``-N`` suffix rather than
    overwriting. ``now`` is injected for deterministic tests; the runtime uses the
    real UTC clock. Receipts are gitignored and pruned from the walk scan, so they
    never affect ``codas check`` / ``codas inventory``.
    """
    now = now or datetime.now(timezone.utc)
    receipt = build_receipt(repo, report, compute_provenance(repo), now)
    directory = repo / ".codas" / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt.to_json(), indent=2, sort_keys=True) + "\n"
    base = _basic(now)
    # Atomic exclusive create ("x") so two concurrent --receipt runs never overwrite
    # (no TOCTOU); bounded retry on a same-second collision picks the next -N name.
    for counter in range(_MAX_RECEIPTS_PER_SECOND):
        name = f"{base}.json" if counter == 0 else f"{base}-{counter}.json"
        path = directory / name
        try:
            with open(path, "x", encoding="utf-8") as handle:
                handle.write(body)
            return path
        except FileExistsError:
            continue
    raise RuntimeError(f"could not allocate a unique receipt name under {directory}")


def _iso(now: datetime) -> str:
    return _utc(now).strftime("%Y-%m-%dT%H:%M:%SZ")


def _basic(now: datetime) -> str:
    return _utc(now).strftime("%Y-%m-%dT%H%M%SZ")


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)
