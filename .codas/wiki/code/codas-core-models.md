`codas-core-models` is the dependency-free vocabulary at the bottom of the Codas stack: three small, stdlib-only modules that every other layer agrees on. `models.py` defines the finding triad — `Evidence` (a path plus optional line/detail), `Finding` (a severity/`check_id`/message carrying its evidence), and `CheckReport` (the per-repo aggregate, whose `has_errors` property derives the exit verdict). `receipt.py` adds `Receipt`, a durable record of a run's inputs, provenance, and result. `provenance.py` supplies the hashing primitives `digest`, `inventory_hash`, and `policy_version` that pin exactly which facts and policy config a run observed.

It exists to be the *shared contract*: every policy under `src/codas/policies` imports `Evidence` and `Finding` and nothing else of Codas to emit results, and `app/check.py` plus `reporting/console.py` consume the same types. By centralizing this shape, a policy author never invents an ad-hoc result format, and the renderer never has to special-case one. The wide fan-in (20-plus policy modules) is the whole point — one vocabulary, many producers, two consumers.

### Invariants it upholds
Two boundaries make this layer trustworthy. First, **purity**: every type is a `@dataclass(frozen=True)` value with a `to_json` method and no I/O — `Receipt` explicitly leaves writing to the app layer. Second, **determinism**: `provenance.py` hashes canonical bytes (`json.dumps(sort_keys=True, separators=...)` with `default=str`), so YAML key order or a stray date never perturbs a hash, and `inventory_hash` deliberately hashes the already-canonical rendered artifact so the hash survives internal refactors. The module imports only `dataclasses`, `hashlib`, and `json` — never adapters, never the app — keeping it the safe foundation the strict adapter boundary rests on.

```atlas:claims
defines: governance finding -> src/codas/core/models.py::::Finding
defines: run receipt -> src/codas/core/receipt.py::::Receipt
defines: provenance hashing -> src/codas/core/provenance.py::::policy_version
```
