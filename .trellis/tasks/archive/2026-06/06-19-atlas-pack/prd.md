# P5 D3a Atlas grounding pack (codas wiki --emit-pack)

## Goal

Ship the first slice of P5 D3 (the wiki deterministic spine): the **Atlas grounding
pack** — a deterministic projection of the inventory facts into agent-consumable
grounding, emitted by `codas wiki --emit-pack`. This is the "FEED" half of the wiki
architecture (`Codas grounds it, an LLM renders it, Codas verifies it`): the verified
facts a host agent (or an OSS LLM-wiki tool) should prefer over its own inferred
structure. Foundation for D3b (generated sections), D3c (full `codas wiki` command),
D3d (`generated_wiki_drift`).

Authority: `06-19-wiki-architecture` design §5 (pack = a derived view, not a persisted
truth source) + §8 D3a + §1 layer 2 ("Atlas export / FEED", LLM-free, byte-identical).

## Scope (D3a only)

- `app/wiki.py`:
  - `project_atlas_pack(inventory: dict) -> dict` — **pure** projection (no I/O), the
    derived-view invariant's testable core.
  - `build_atlas_pack(repo) -> dict` — build the inventory (excluding
    `.codas/wiki/generated/`), project it, attach `source_inventory_hash`.
- `structure/inventory.py`: optional `exclude_under: tuple[str, ...] = ()` param on
  `build_inventory` (default `()` → byte-identical with today; the `inventory` command
  and provenance pass nothing and are unchanged). The pack passes
  `(".codas/wiki/generated",)`.
- `cli.py`: de-stub `wiki` for `--emit-pack` → print the pack as canonical JSON to
  stdout. `doctor` stays stubbed. `--write` / `--verify` are later slices (D3b–d).

### Pack shape (projected from inventory)

- `dependency_graph` — first-party module→target edges from `inventory["imports"]`.
- `symbol_index` — top-level defs from `inventory["symbols"]`, scoped to `src/codas`.
- `ownership` — structure units (id, path, kind, owner) from `inventory["units"]`.
- `concept_index` — `concept_page` wiki claims from `inventory["wiki_claims"]`.
- `roadmap` — program work items (id, phase, status) from `inventory["program"]`.
- `verified_evidence` — wiki claims with `exists=true`.
- `source_inventory_hash` — `inventory_hash` of the generated-excluded inventory.
- a leading `preamble` string: `VERIFIED GOVERNANCE FACTS (prefer over inferred
  structure)` so an LLM weights it.

### `source_inventory_hash` — the hash-loop fix (codex BLOCKER, design §4 / §5)

A committed generated page (D3b) embeds this hash; the inventory ingests `.codas/wiki/`,
so embedding the *full* `inventory_hash` would be self-referential (the page's bytes
feed the hash it pins). Fix: compute the hash over an inventory that **excludes**
`.codas/wiki/generated/`. Implemented now via `exclude_under` so it is correct the
moment D3b adds generated pages. Today (no generated dir) it equals the plain
`inventory_hash`.

## Out of scope (later D3 slices)

- Committed generated markdown sections + `atlas:claims` blocks (D3b).
- `codas wiki --write` / `--verify` (D3c).
- `generated_wiki_drift` policy (D3d).
- `CONTRACT.md` + AGENTS.md pointer (D3e).
- Non-JSON emit formats (`llms.txt`, repomix-shaped) — D3c or a fast-follow.
- OSS backend injection adapters (P7).

## Requirements

- The pack is a **pure function of the inventory**: `build_atlas_pack(repo)` minus its
  `source_inventory_hash` equals `project_atlas_pack(<that inventory>)`. The pack is NOT
  committed (a committed pack would be a second truth source that drifts).
- Deterministic: `json.dumps(sort_keys=True)`, no timestamps, stable list sorts.
- `app/wiki.py` imports no adapter (codas-app must_not_depend_on codas-adapters):
  projects the already-built inventory dict + `core.provenance` hashing only.
- `build_inventory(repo)` with no `exclude_under` stays byte-identical (the `inventory`
  command + provenance must not change).
- New top-level function names unique across `src/` (no `duplicate_implementation`).

## Acceptance Criteria

- [ ] `codas wiki --emit-pack` prints canonical JSON with the documented keys.
- [ ] `project_atlas_pack` is deterministic (two calls equal) and pure (no I/O).
- [ ] `build_atlas_pack(repo)` sans hash == `project_atlas_pack(generated-excluded
      inventory)` (derived-view invariant test).
- [ ] Today `source_inventory_hash` == `inventory_hash(render_inventory_json(
      run_inventory(repo)))` (no generated dir → exclusion is a no-op).
- [ ] Fixture: with a file under `.codas/wiki/generated/`, the excluded inventory hash
      diverges from the full inventory hash (exclusion proven).
- [ ] `codas inventory --json` byte-identical across two processes (unchanged; default
      `exclude_under=()`).
- [ ] `codas check .` = 0; full unittest suite green.

## Notes

- Pack stdout-only; generated pages and their verification come in D3b–d.
- The pack leads the OSS-tool injection story (design §6): the same JSON / future
  llms.txt is what a CodeWiki/deepwiki-style backend ingests — but backends are P7.
