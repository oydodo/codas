# Design — P4 C2: receipt ledger

Authority: CONTEXT.md (Receipt), plan §3 (Receipt is a core model), §12 (repo
state: `.codas/receipts/<ts>.json`, gitignored). Builds on C1 provenance.

## Core model: `src/codas/core/receipt.py` (pure)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Receipt:
    timestamp: str                 # ISO-8601 UTC, e.g. 2026-06-18T12:00:00Z
    repo: str
    provenance: dict               # {inventory_hash, policy_version}
    ok: bool
    error_count: int
    warning_count: int
    findings: list                 # the check's findings JSON (report.to_json()["findings"])

    def to_json(self) -> dict:
        return {
            "schema_version": 1,
            "kind": "receipt",
            "timestamp": self.timestamp,
            "repo": self.repo,
            "provenance": self.provenance,
            "result": {
                "ok": self.ok,
                "error_count": self.error_count,
                "warning_count": self.warning_count,
            },
            "findings": self.findings,
        }
```

No I/O, no app import — a Receipt is a value. (Layering: core stays pure.)

## App: `src/codas/app/receipt.py`

```python
from datetime import datetime, timezone
from pathlib import Path
from codas.app.provenance import compute_provenance
from codas.core.models import CheckReport
from codas.core.receipt import Receipt

def build_receipt(repo: Path, report: CheckReport, provenance: dict, now: datetime) -> Receipt:
    findings = [f.to_json() for f in report.findings]
    return Receipt(
        timestamp=_iso(now),
        repo=repo.as_posix(),
        provenance=provenance,
        ok=not report.has_errors,
        error_count=sum(f.severity == "error" for f in report.findings),
        warning_count=sum(f.severity == "warning" for f in report.findings),
        findings=findings,
    )

def write_receipt(repo: Path, report: CheckReport, now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    receipt = build_receipt(repo, report, compute_provenance(repo), now)
    directory = repo / ".codas" / "receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = _unique_path(directory, _basic(now))          # never overwrite (append-only)
    path.write_text(json.dumps(receipt.to_json(), indent=2, sort_keys=True) + "\n")
    return path
```

(`import json` at top — the BLOCKER fix.) `_unique_path(directory, base)` returns
`base.json`, else `base-1.json`, `base-2.json`, … — the first free name — so two
receipts in the same second never silently overwrite (honors the append-only
framing).

- `_iso(now)` → `now.astimezone(timezone.utc)` formatted `%Y-%m-%dT%H:%M:%SZ`.
- `_basic(now)` → same without colons: `%Y-%m-%dT%H%M%SZ` → matches the §12 example
  `2026-06-17T120000Z.json` (filesystem-safe).
- `now` is injected (default `datetime.now(timezone.utc)`) so tests pin it and
  assert byte-stable bodies; the runtime uses the real clock. (Receipts are
  deliberately non-deterministic across runs — they record *when* — but the body is
  a pure function of (report, provenance, now).)
- Determinism note: `datetime.now`/`new Date` are fine in the codas RUNTIME (a real
  product writing a timestamped artifact); the determinism discipline applies to
  `check`/`inventory` OUTPUT, which this does not touch.

## CLI: `codas check --receipt`

Add a `--receipt` flag to the `check` subparser. The receipt path must NOT be
printed to stdout in `--json` mode (it would corrupt the JSON report). So:

```python
receipt_path = write_receipt(repo, report) if args.receipt else None
if args.json:
    payload = report.to_json()
    payload["provenance"] = compute_provenance(repo)
    if receipt_path is not None:
        payload["receipt"] = str(receipt_path)     # structured, not a stray print
    print(json.dumps(payload, indent=2, sort_keys=True))
else:
    print_findings(report.findings)
    if receipt_path is not None:
        print(f"Receipt written: {receipt_path}")
```

Order: write the receipt before returning the exit code, so a failing check still
records its receipt. Default `codas check` (no flag) is unchanged.

## Dogfooding / determinism

- `.codas/receipts/*.json` is already gitignored, and `discover_files` uses
  `git ls-files --exclude-standard` → receipts never enter the scan → no
  `missing_owner`/`structure_drift`/`orphan` finding, and `codas inventory` is
  unaffected. `codas check .` stays 0.
- **Non-git fallback fix (codex C2 review).** `discover_files` falls back to
  `_walk_files` when git is absent, and that path does NOT honor `.gitignore` —
  so a written receipt would be scanned on a fresh/detached checkout, breaking
  `check .=0` + inventory determinism. Fix `_walk_files` to prune the
  `.codas/receipts` subtree (a known generated-artifact dir), so receipts are
  invisible on BOTH the git and walk paths. `structure/index.py` is owned by
  `codas-structure-module`.
- New modules `core/receipt.py` (owned by `codas-core-models`) + `app/receipt.py`
  (owned by `codas-app`) — no new structure unit; inventory auto-picks their
  symbols. `app/receipt.py → app/provenance + core` is downward; with the broadened
  P3 rules `codas-app must_not_depend_on codas-adapters` — receipt imports no
  adapter, so dependency-direction stays 0.
- Symbol names `Receipt`/`build_receipt`/`write_receipt`/`_iso`/`_basic` must be
  unique top-level under `src/` (duplicate_implementation guard) — verify.

## Tests (`tests/test_receipt.py`)

- `build_receipt` with a fixed `now` (e.g. `datetime(2026,6,18,12,0,0,tzinfo=utc)`)
  → deterministic `to_json()`; timestamp `2026-06-18T12:00:00Z`.
- `write_receipt` in a temp repo → file at
  `.codas/receipts/2026-06-18T120000Z.json`, parses, `provenance` ==
  `compute_provenance(repo)`, `result.ok` matches, dir auto-created.
- error/warning counts correct for a report with mixed severities (construct a
  `CheckReport` with synthetic findings).
- `codas check . --receipt` (subprocess in a temp repo) prints `Receipt written:`
  and the file exists; `codas check .` (no flag) writes nothing.
- non-UTC `now` is normalized to UTC `Z` in both the body and the filename.

## Open questions for codex design review

- Opt-in `--receipt` flag vs always-write (gitignored) — flag chosen to avoid
  surprise files and keep default check side-effect-free; agree?
- Receipt embeds the FULL findings JSON (durable record) vs a summary only — full
  chosen for completeness; any size/utility concern?
- `repo` as `repo.as_posix()` (absolute path, machine-specific) in the receipt —
  acceptable since a receipt is a local/CI artifact recording *this* run, not a
  portable/deterministic artifact? Or store a repo-relative marker instead?
- Filename collision if two receipts are written in the same second — overwrite vs
  uniquify (append a short counter/hash)? Proposal: accept second-granularity
  overwrite for C2; finer identity is a later facet.
