# Design — P4 C3: preflight context pack

Authority: CONTEXT.md (Context Pack), plan §8 (P4 "task context pack"), §5
(Preflight app service). Builds on C1 provenance + the existing Trellis/config
loaders.

## App: `src/codas/app/preflight.py`

```python
from pathlib import Path
from codas.adapters.trellis import extract_task_facts
from codas.app.provenance import compute_provenance
from codas.config.loader import load_codas_config, load_policies

def build_context_pack(repo: Path, task_id: str | None = None) -> dict:
    config = load_codas_config(repo / ".codas" / "config.yml")
    tasks = extract_task_facts(repo, config)

    task = None
    if task_id is not None:
        match = next((t for t in tasks.items if t.id == task_id), None)
        if match is not None:
            task = {
                "id": match.id, "status": match.status, "package": match.package,
                "dev_type": match.dev_type, "priority": match.priority,
                "archived": match.archived,
            }

    policies_raw = load_policies(repo / ".codas" / "policies.yml")
    declared = policies_raw.get("policies", {})
    policies = sorted(
        ({"id": pid, "severity": (body or {}).get("severity")} for pid, body in declared.items()),
        key=lambda p: p["id"],
    )

    return {
        "schema_version": 1,
        "kind": "context_pack",
        "task": task,
        "available_tasks": sorted(t.id for t in tasks.items),
        "read_first": sorted(config.authoritative_sources),
        "supporting": sorted(config.supporting_sources),
        "dogfooding_protocol": config.dogfooding_protocol,
        "policies": policies,
        "provenance": compute_provenance(repo),
    }
```

- **Layering:** app -> adapters? No — `app.preflight` imports `codas.adapters.trellis`.
  Is that a boundary violation? The §11 boundary forbids **core** (policies, core
  models) from importing adapters; **app services** legitimately orchestrate
  adapters + engines (plan §3: "Application services orchestrate engines"; engines
  use adapter protocols). `codas.structure.inventory` (the bridge) and now
  `app.preflight` consume the Trellis adapter to assemble facts — allowed. The
  dependency-direction rules only forbid `codas-app -> codas-adapters`... **wait:**
  the P3-review hardening added `codas-app must_not_depend_on codas-adapters`. So
  `app/preflight.py` importing `codas.adapters.trellis` WOULD fire dependency-direction
  (error) and break `check .=0`.
  → **Resolution:** consume task facts the same neutral way the boundary intends —
  go through the inventory facts, not the adapter directly. Use
  `run_inventory(repo)["tasks"]["items"]` (already the normalized task facts in the
  inventory) instead of importing `codas.adapters.trellis`. That keeps
  `app.preflight` adapter-free and the broadened boundary green. (Same for any other
  fact: read it from the inventory, the canonical fact surface.)

### Revised: single inventory snapshot, adapter-free (codex C3 #1 + #3)

Run the inventory ONCE and derive BOTH the task facts and the `inventory_hash` from
that same snapshot — never call `run_inventory` twice (tasks via one call,
provenance via another), or `task`/`available_tasks` could diverge from
`provenance.inventory_hash` if the tree mutates between calls. Do NOT import
`codas.adapters.trellis` (it would fire `codas-app -> codas-adapters`); read the
normalized task facts from the inventory's `tasks` block instead.

```python
from codas.app.inventory import render_inventory_json, run_inventory
from codas.config.loader import load_codas_config, load_policies
from codas.core.provenance import inventory_hash, policy_version

def build_context_pack(repo: Path, task_id: str | None = None) -> dict:
    config = load_codas_config(repo / ".codas" / "config.yml")
    inventory = run_inventory(repo)                                  # single snapshot
    inv_hash = inventory_hash(render_inventory_json(inventory))
    policies_raw = load_policies(repo / ".codas" / "policies.yml")

    task_items = inventory.get("tasks", {}).get("items", [])
    task = next((t for t in task_items if t.get("id") == task_id), None) if task_id else None
    declared = policies_raw.get("policies", {}) or {}
    return {
        "schema_version": 1,
        "kind": "context_pack",
        "task": task,                                  # the inventory task dict (or None)
        "available_tasks": sorted(t.get("id") for t in task_items),
        "read_first": sorted(config.authoritative_sources),
        "supporting": sorted(config.supporting_sources),
        "dogfooding_protocol": config.dogfooding_protocol,
        "policies": sorted(
            ({"id": pid, "severity": (body or {}).get("severity")} for pid, body in declared.items()),
            key=lambda p: p["id"],
        ),
        "provenance": {"inventory_hash": inv_hash, "policy_version": policy_version(policies_raw)},
    }
```

`app.preflight -> app.inventory + app.provenance(core) + config.loader` — all
app/down, no adapter import. `provenance` values equal `compute_provenance(repo)`
for a valid repo (same hash functions, same inputs), so tests can assert equality.
Preflight is a precondition tool: a missing/malformed `.codas/config.yml` raises
(fail loudly) rather than best-effort — config is required to preflight.

`print_context_pack(pack)` lives in `reporting/console.py` and must be imported in
`cli.py` alongside `print_findings`.

## CLI: implement `preflight`

`cli.py` currently routes `preflight` to the "planned but not implemented" stub.
Replace with:

```python
if args.command == "preflight":
    from .app.preflight import build_context_pack
    pack = build_context_pack(repo, task_id=args.task)
    if args.json:
        print(json.dumps(pack, indent=2, sort_keys=True))
    else:
        print_context_pack(pack)   # small human summary in reporting/console.py
    return 0
```

Add `--json` to the `preflight` subparser (it already has `repo` + `--task`). Keep
`wiki`/`doctor` in the stub branch.

## Determinism / dogfooding

- The pack is deterministic: sorted lists, provenance content-hashes, NO timestamp
  (timestamps live on the receipt). Two runs at one commit → identical pack.
- `app/preflight.py` owned by `codas-app`; imports `app.inventory` + `app.provenance`
  + `config.loader` — all downward / same-layer, NO adapter import → dependency
  direction stays 0, check stays 0.
- New public symbols `build_context_pack` (+ `print_context_pack` in reporting) must
  be unique top-level under `src/` (duplicate_implementation) — verify.
- No new governance file / structure unit.

## Tests (`tests/test_preflight.py`)

- `build_context_pack(repo)` (temp repo): `read_first` == sorted authoritative
  sources; `policies` lists each declared id+severity; `provenance` ==
  `compute_provenance(repo)`; deterministic across two calls.
- `--task <id>`: a temp repo with a Trellis task → `task` populated; unknown id →
  `task` None; no task_id → `available_tasks` lists the ids, `task` None.
- `codas preflight . --json` (subprocess) emits parseable JSON with the expected
  keys; `codas preflight .` (human) prints a summary and exits 0.
- check . stays 0 after adding the command (regression).

## Open questions for codex design review

- Sourcing task facts via `run_inventory(repo)["tasks"]` to stay adapter-free
  (honoring the broadened `codas-app must_not_depend_on codas-adapters` rule) vs
  importing `codas.adapters.trellis` directly — confirm the inventory-fact route is
  the right boundary-respecting choice.
- Pack contents for C3 (task + read_first + policies + provenance) — enough for a
  useful first cut, with risks/required-updates deferred?
- `available_tasks` when no `--task` — helpful, or noise? Alternative: omit and
  require `--task`.
- preflight error behavior on missing/malformed `.codas/config.yml` — fail loudly
  (it is a precondition) vs best-effort like provenance?
