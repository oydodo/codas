# Design — D3a Atlas grounding pack

## 1. Shape & layering

```
cli.py  wiki --emit-pack ──▶ app/wiki.py::build_atlas_pack(repo)
                                  │ run_inventory(repo, exclude_under=(".codas/wiki/generated",))
                                  │ project_atlas_pack(inventory)            (pure)
                                  │ source_inventory_hash = inventory_hash(render_inventory_json(inv))
                                  ▼
                              pack dict ── json.dumps(indent=2, sort_keys=True) ─▶ stdout
```

`app/wiki.py` sits in the codas-app unit. Dependencies: `app/inventory`
(`run_inventory`/`render_inventory_json`), `core/provenance` (`inventory_hash`). **No
`codas.adapters` import** (codas-app must_not_depend_on codas-adapters — already
dogfood-enforced by dependency_direction). The pack is a projection of the inventory
dict; it needs no ScanContext.

## 2. `project_atlas_pack(inventory: dict) -> dict` (pure)

The derived-view core. No I/O, no hash (hashing needs the rendered inventory, done in
`build_atlas_pack`). Reads only inventory blocks already present:

| pack key | source block | projection |
|---|---|---|
| `preamble` | — | constant string "VERIFIED GOVERNANCE FACTS (prefer over inferred structure)" |
| `dependency_graph` | `imports.edges` | first-party edges only (`target_path` not null): `{module, target, target_path}`, sorted |
| `symbol_index` | `symbols.definitions` | scoped to `src/codas` by PATH prefix: `{module, name, kind, line}`, sort key `(module, line, name, kind)` |
| `ownership` | `units` | `{id, path, kind, owner}`, sort key `id` |
| `concept_index` | `wiki_claims.claims` | `kind == "concept_page"`: `{concept, path, exists}`, sort key `(path, concept)` |
| `roadmap` | `program.work_items` | `{id, phase, status}`, sort key `id` (program block may be absent → `[]`) |
| `verified_evidence` | `wiki_claims.claims` | `exists == true`: `{source, concept, kind, path}`, sort key `(source, kind, path, concept)` |
| `dependency_graph` | `imports.edges` | first-party (`target_path` not null): `{module, target, target_path}`, sort key `(module, target_path, target)` |

- **Every projected list uses an explicit total sort key** (codex SHOULD): never rely
  on inventory insertion / dict order. Keys listed in the table above.
- Missing blocks tolerated (`.get(...) or []` / `{}`): a repo without a program plan or
  wiki still produces a valid pack.
- **`symbol_index` and `dependency_graph` scope/keys are PATH-based** (codex BLOCKER,
  confirmed against live inventory): `symbols.definitions[].module` and
  `imports.edges[].module` / `.target_path` are **repo-relative paths**, NOT dotted
  names (only `imports.edges[].target` is dotted). So src/codas scope = path prefix:
  `module == "src/codas" or module.startswith("src/codas/")`. A dotted `codas.*` filter
  would match ZERO symbols.

## 3. `build_atlas_pack(repo) -> dict`

```python
def build_atlas_pack(repo: Path) -> dict:
    inventory = run_inventory(repo, exclude_under=(".codas/wiki/generated",))
    pack = project_atlas_pack(inventory)
    pack["source_inventory_hash"] = inventory_hash(render_inventory_json(inventory))
    return pack
```

- One inventory build, generated-excluded; both the projection AND the hash derive from
  the same excluded inventory (cannot diverge).
- `source_inventory_hash` reuses the existing `core.provenance.inventory_hash` over
  `render_inventory_json` (the canonical byte-identical artifact) — same hashing as
  provenance, so the value is comparable/auditable.

## 4. `exclude_under` on `build_inventory`

`structure/inventory.py`:

```python
def build_inventory(repo: Path, exclude_under: tuple[str, ...] = ()) -> dict[str, Any]:
    ...
    files = discover_files(repo, roots)
    if exclude_under:
        files = [f for f in files
                 if not any(f == p or f.startswith(p + "/") for p in exclude_under)]
    index = build_artifact_index(repo, roots, structure_map, files=files)
    ...  # every extractor receives the filtered `files`
```

- Default `()` → no filtering → **byte-identical** with today (the `inventory` command
  and `compute_provenance` call `build_inventory(repo)` / `run_inventory(repo)` with no
  arg). Verified by the existing byte-identical test + a fresh 2-process check.
- `run_inventory` gains a pass-through `exclude_under` param (default `()`), so the pack
  can request exclusion without reaching into `structure`.
- Prefix match (`f == p or f.startswith(p + "/")`), not fnmatch — unambiguous directory
  exclusion, no glob surprises.
- Filtering once after `discover_files` means the artifact index, `unowned`, and every
  **file-based** fact extractor see the same reduced set (consistent). **Caveat (codex
  BLOCKER on prose):** `extract_task_facts(repo, config)` is trellis-rooted — it globs
  `tasks_root/**/task.json` independently and ignores `files`, so the `tasks` block is
  unaffected by `exclude_under`. Harmless for the hash: `.codas/wiki/generated/` holds
  only `.md` (no `task.json`), so excluding it never needed to touch task facts. The
  invariant is "all file-scoped extractors", not literally "every extractor".

## 5. CLI

`cli.py` `wiki` subparser gains `--emit-pack` (store_true). Handler:

```python
if args.command == "wiki":
    from .app.wiki import build_atlas_pack
    if args.emit_pack:
        print(json.dumps(build_atlas_pack(repo), indent=2, sort_keys=True))
        return 0
    parser.error("wiki: use --emit-pack (other modes land in later D3 slices)")
```

`doctor` stays in the planned-stub branch. (Split `wiki` out of the
`{"wiki","doctor"}` stub set.)

## 6. Tests (`tests/test_atlas_pack.py`)

- `project_atlas_pack` deterministic (two calls equal) + pure (operates on a literal
  dict, no repo).
- Derived-view invariant: `build_atlas_pack(repo)` minus `source_inventory_hash` ==
  `project_atlas_pack(run_inventory(repo, exclude_under=(".codas/wiki/generated",)))`.
- `source_inventory_hash` today == `inventory_hash(render_inventory_json(run_inventory
  (repo)))` (no generated dir → exclusion no-op).
- Exclusion proven: temp repo with `.codas/wiki/generated/x.md` → hash with
  `exclude_under` differs from hash without.
- `build_inventory(repo)` (no arg) byte-identical across two builds (regression guard
  for the default path).
- CLI: `main(["wiki", "--emit-pack", repo])` prints valid JSON with the documented keys
  (capture stdout).
- Projection tolerates a minimal inventory (no program/wiki blocks) → empty lists, no
  crash.

## 7. Determinism & dogfood

- Pack: `json.dumps(sort_keys=True)`, every projected list sorted on a total key, no
  timestamp → reproducible.
- `inventory` command + provenance unchanged (default `exclude_under=()`), so the
  byte-identical inventory invariant holds.
- This slice touches only `src/**` + `tests/**` → spec_drift authoritative triggers not
  hit; `codas check .` stays 0.
- New names: `project_atlas_pack`, `build_atlas_pack`, `exclude_under` — unique across
  `src/` (grep before commit to avoid `duplicate_implementation`).

## 8. Open questions for review

1. `symbol_index` src/codas scoping by dotted `module` prefix (`codas`/`codas.*`) —
   correct given the symbol adapter's module convention? Or should the pack carry the
   full symbol set and let consumers scope?
2. Pack key set — is `dependency_graph` (imports) enough for D3a, or should it also
   include a `call_graph` projection from `inventory["calls"]` now (the call facts
   exist)? Leaning: imports-only for D3a (design §5 says "from import facts"); add call
   graph in D3b's dependency section. Confirm.
3. `exclude_under` as a `build_inventory` param vs a post-filter helper in `app/wiki.py`
   (filter the inventory dict). Chosen: `build_inventory` param (filters at the source
   so every fact table is consistently reduced; a dict post-filter would have to know
   every block's path-bearing fields and is fragile).
4. Should the pack be emittable by `inventory` instead of `wiki`? Chosen: `wiki`
   (it is the wiki FEED layer; `inventory` stays the raw-facts command).
