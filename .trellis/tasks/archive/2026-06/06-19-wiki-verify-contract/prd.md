# P5 D3 closeout: codas wiki --verify + CONTRACT.md

## Goal

Close out P5 D3 (the wiki deterministic spine) with the two remaining slices, then mark
P5 complete:

- **D3c — `codas wiki --verify`**: the freshness/integrity command (the home for the
  source-hash freshness deferred from D3d). Re-renders each committed generated page and
  compares to on-disk; any mismatch (stale or hand-edited) is reported, exit nonzero —
  CI-usable, opt-in, NOT the always-on `check` gate.
- **D3e — CONTRACT.md**: the host-agent authoring contract (the "schema" layer of the
  Atlas-as-LLM-wiki: Karpathy raw/wiki/**schema**). States what is governed (generated
  sections + atlas:claims, verified) vs supporting (hand-authored prose, non-
  authoritative), and the author workflow (emit-pack -> write -> verify). Registered as
  a governed doc + a pointer from AGENTS.md (outside the Trellis-managed block) and the
  wiki index.

Implements design `06-19-wiki-architecture` §8 D3c + D3e, §5 (render-vs-ondisk drift),
§3 link ②.

## D3c scope

- `app/wiki.py`: factor the render into `_generated_pages(repo) -> dict[Path, str]`
  (shared by `--write`); `verify_generated_sections(repo) -> list[Path]` returns the
  STALE pages (on-disk != fresh render). `--verify` subsumes source_inventory_hash
  freshness: the hash is part of the rendered bytes, so a byte-compare catches a stale
  hash AND a hand-edit in one check — no separate hash logic.
- `cli.py`: `--verify` added to the wiki mutually-exclusive group; prints stale pages or
  "up to date"; exit 1 if any stale, else 0.
- **Regenerate** `.codas/wiki/generated/governance.md` in this slice (it is stale-by-
  source from the D3b/c/d commits) so `codas wiki --verify` is clean at P5 close.

## D3e scope

- `CONTRACT.md` (repo root): the authoring contract. Content (concise):
  - Only `.codas/wiki/generated/**` + `atlas:claims` blocks are GOVERNED/verified;
    hand-authored concept-page prose is supporting-tier and cannot out-rank facts (§2).
  - A generated page MUST embed a nonempty `atlas:claims` block + `source_inventory_hash`
    (else `generated_wiki_drift` error).
  - `atlas:claims` grammar `key: subject -> value` (`unit:`/`roadmap:`/
    `source_inventory_hash:`); every claim must be true vs facts (verified, false=error).
  - Workflow: ground with `codas wiki --emit-pack`; (re)generate with `codas wiki
    --write`; check with `codas wiki --verify` + `codas check`; never hand-edit generated
    pages.
- Register CONTRACT.md as governed:
  - `structure.yml`: new `wiki-contract` unit (path `CONTRACT.md`, owner Orientation
    Curator); add to `repo-root.allowed_children`.
  - `config.yml`: add `CONTRACT.md` to `constraint_sources.supporting`.
  - `documents.yml`: add a `wiki_contract` role (path `CONTRACT.md`, supporting).
  - `AGENTS.md`: a one-line pointer AFTER `<!-- TRELLIS:END -->` (preserved region).
  - `.codas/wiki/index.md`: a pointer to `CONTRACT.md` (link, not a canonical source).

The AGENTS.md contract-CHECK (verify it names real subcommands + points at a real
CONTRACT.md) is deferred to P6 per design §3 link ②.

## Dogfood-cleanliness (must hold)

- After regenerating governance.md, `codas wiki --verify` exits 0; `codas check .` = 0.
- CONTRACT.md owned by the new `wiki-contract` unit (no `missing_owner`); declared in
  config (so a wiki canonical/link reference to it passes `stale_wiki_claim`/
  `stale_claim`); its own prose uses no claim-creating wiki headings.
- The new structure unit's path (`CONTRACT.md`) exists → no `structure_drift`.
- `inventory --json` byte-identical (CONTRACT.md + the registrations are deterministic
  facts; verify across two processes).

## Acceptance Criteria

- [ ] `codas wiki --verify` exits 0 when generated pages are fresh, 1 (listing stale
      pages) when not; a fixture proves the stale path.
- [ ] `--verify`/`--write`/`--emit-pack` mutually exclusive; covered by a test.
- [ ] governance.md regenerated -> `codas wiki --verify` clean on the real repo.
- [ ] CONTRACT.md present, registered (structure unit + config supporting + documents
      role), pointed to from AGENTS.md (post-END) + wiki index.
- [ ] `codas check .` = 0; `inventory --json` byte-identical; full suite green.
- [ ] program.yml P5 -> `completed` with exit criteria met; P6 unblocked.

## Notes

- `--verify` byte-compare is the clean freshness check: re-render == on-disk. No hash
  bookkeeping; the embedded source_inventory_hash rides along in the bytes.
- This closes the deterministic wiki spine (P5 D3). P6 = enforcement hooks (gate `codas
  check`, wiki enforced for free). The two queued big tasks (incremental-fact-cache,
  spec-drift-fact-delta) remain independent.
