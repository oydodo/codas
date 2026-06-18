# Design — P4 C1: provenance hashes

Authority: `docs/codas-implementation-plan.html` §8 (P4 row), §12 (repo state:
`receipts/`), CONTEXT.md (Receipt, Gate). Core domain already lists `Receipt`
(plan §3) — this slice ships the provenance primitives it needs.

## Layering: pure core digests + app-layer orchestration

Dependencies point downward (plan §3: "Core domain must not import ... product
integration"; engines/app depend on core, never the reverse). So the **pure digest
primitives live in core** (no I/O, no app import) and the **orchestration lives in
app** (it runs the inventory engine + loads config — an application service job).

`src/codas/core/provenance.py` (pure, stdlib only):

```python
import hashlib, json

def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

def inventory_hash(inventory_json: str) -> str:
    return digest(inventory_json)

def policy_version(policies_raw: dict) -> str:
    # default=str: raw SafeLoader values may include non-JSON types (e.g. a YAML
    # date); coerce deterministically so canonical serialization never fails.
    return digest(
        json.dumps(policies_raw, sort_keys=True, separators=(",", ":"), default=str)
    )
```

`src/codas/app/provenance.py` (orchestration):

```python
from pathlib import Path
from codas.app.inventory import render_inventory_json, run_inventory
from codas.config.loader import load_policies
from codas.core.provenance import inventory_hash, policy_version

def compute_provenance(repo: Path) -> dict:
    inventory_json = render_inventory_json(run_inventory(repo))
    policies = load_policies(repo / ".codas" / "policies.yml")
    return {
        "inventory_hash": inventory_hash(inventory_json),
        "policy_version": policy_version(policies),
    }
```

- **Why hash the inventory *output*, not internals.** The byte-identical
  `codas inventory --json` is the public contract; hashing it makes the
  inventory_hash robust to internal refactors (e.g. a future build_inventory /
  ScanContext unification) — same facts ⇒ same hash. Determinism is inherited from
  the inventory's existing byte-identical guarantee.
- **policy_version** hashes the *declared* policy config (severities/options), the
  thing that defines "which check ran". Canonical `json.dumps(sort_keys=True)` so
  YAML key order never changes the hash. (Engine/code version is a later facet.)
- Clean direction: `app.provenance → core.provenance` (down) + `app.provenance →
  app.inventory` + `config.loader`. No core→app edge.

### Determinism notes (codex C1 review)

- **Canonical inventory artifact = the string returned by `render_inventory_json()`
  verbatim (no trailing newline).** The CLI adds a newline via `print`, so the
  hashed artifact is the render-function output, not stdout. Documented so anyone
  reproducing the hash uses the same bytes. The C1 test asserts
  `check --json` provenance equals `inventory_hash(render_inventory_json(run_inventory(cwd)))`.
- **List order is machine-stable.** Every inventory array is emitted in a
  total-key sort by its source: doc_claims sorted `(source,line,path,fragment,kind)`,
  symbols `(module,line,name,kind)`, imports `(module,line,target)`, units/documents
  by id/role, tasks by the trellis extractor's order (verify it sorts by a total
  key — if not, sort in C1). `discover_files` returns sorted paths. So at a given
  commit the full inventory JSON — hence its hash — is identical across machines.
- **Scope caveat (waivers excluded).** `provenance = inventory + declared policy
  config`. It pins *which facts* and *which policy declarations* a run saw — NOT the
  fully-effective check inputs, since `waivers.yml` (which suppresses findings) is
  out of scope for C1. A `waiver_version` is a C2/later addition when the receipt
  needs to prove suppression state. Consumers must read the block as
  "inventory+policy version", not "complete check provenance".

## Surface: `codas check --json`

In `cli.py`, the `check` `--json` branch merges provenance into the payload:

```python
from .app.provenance import compute_provenance
...
payload = report.to_json()
payload["provenance"] = compute_provenance(repo)
print(json.dumps(payload, indent=2, sort_keys=True))
```

`run_check` stays findings-only (fast, pure, unchanged) — provenance is assembled at
the CLI/report boundary, so the default human `codas check` and the unit-tested
`run_check` are untouched. The deterministic `codas inventory --json` output is NOT
modified (no self-referential hash embedded in the inventory).

## Determinism / dogfooding

- `inventory_hash` is byte-stable because inventory JSON is byte-identical x2.
  `policy_version` is byte-stable (sorted canonical dump). Independent: changing a
  fact moves only inventory_hash; changing a severity moves only policy_version.
- `core/provenance.py` is owned by `codas-core-models` (path `src/codas/core`);
  `app/provenance.py` by `codas-app` (path `src/codas/app`). No new structure unit
  (both under existing units); inventory picks up the new symbol sources
  automatically.
- `check .` stays 0 (provenance never emits a finding). No new governance file.
- Symbol-name collisions (duplicate_implementation guard): the public names
  `digest` / `inventory_hash` / `policy_version` / `compute_provenance` must be
  unique top-level symbols under `src/` — verify none already exist (esp. that
  `inventory_hash`/`policy_version` don't clash with a later same-name helper).
  Public, single-definition ⇒ no duplicate finding.
- dependency-direction stays 0: `app.provenance → core.provenance` is downward;
  no `codas-app must_not_depend_on` rule exists, and core imports no app.

## Tests (`tests/test_provenance.py`)

- `compute_provenance(repo)` twice → identical dict; both values match
  `"sha256:" + 64 hex`.
- two repos differing by one `.py` symbol → different `inventory_hash`, and (same
  policies) identical `policy_version`.
- flipping a severity in a temp `policies.yml` → different `policy_version`, same
  `inventory_hash`.
- `codas check . --json` (subprocess) includes `provenance` and its
  `inventory_hash` equals `inventory_hash(cwd)`.

## Open questions for codex design review

- Hashing the full inventory JSON (includes symbols/imports/doc_claims/tasks) vs a
  narrower "facts only" subset — is the full canonical inventory the right thing to
  pin as "inventory version"? (It is the byte-identical artifact agents consume.)
- `policy_version` over `policies.yml` raw mapping only — should it also fold in
  `waivers.yml` (active waivers change effective check outcomes)? Proposal: keep C1
  to policies.yml; add a `waiver_version` later if receipts need it.
- Layering split (resolved): pure digests in `core/provenance.py`, orchestration in
  `app/provenance.py` (app→core, no core→app). Confirm this is the right home vs
  putting everything in `app/`.
