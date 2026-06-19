# Design — P5 D3 closeout (wiki --verify + CONTRACT.md)

## 1. D3c — `codas wiki --verify`

Factor the render so `--write` and `--verify` share one source of truth:

```python
def _generated_pages(repo) -> dict[Path, str]:
    inv = run_inventory(repo, exclude_under=(_GENERATED_DIR,))
    h = inventory_hash(render_inventory_json(inv))
    return {repo / _GENERATED_DIR / _GENERATED_PAGE: render_generated_overview(inv, h)}

def write_generated_sections(repo) -> list[Path]:
    out = []
    for path, content in _generated_pages(repo).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        out.append(path)
    return out

def verify_generated_sections(repo) -> list[Path]:   # returns STALE pages
    stale = []
    for path, content in _generated_pages(repo).items():
        if not path.exists() or path.read_text() != content:
            stale.append(path)
    return stale
```

- `--verify` = "every committed generated page is byte-identical to a fresh render".
  The embedded `source_inventory_hash` rides along in the bytes → a stale hash OR a
  hand-edit both surface as a mismatch. No separate freshness logic.
- CLI: `--verify` in the wiki mutually-exclusive group; `verify_generated_sections`;
  stale → print each + `return 1`; clean → print "generated sections up to date" +
  `return 0`. (Precedence in the handler: write, then verify, then emit-pack, else
  usage error — all mutually exclusive so order is cosmetic.)
- Refactor keeps `render_generated_overview` / the hash path unchanged → governance.md
  bytes are identical to D3b's output (after regeneration).

## 2. Regenerate governance.md

Run `codas wiki --write` LAST in this slice (after CONTRACT.md + all registrations
exist), so the page's `source_inventory_hash` reflects the final tree and `--verify`
is clean at commit. (The page's unit/roadmap CLAIMS are unaffected by adding a unit?
NO — adding the `wiki-contract` unit ADDS a `unit: wiki-contract -> CONTRACT.md` row +
claim. So governance.md MUST be regenerated after the structure.yml edit, else
`generated_wiki_drift` would NOT fire (the new unit is simply absent from the page, not
contradicted) but `--verify` would show it stale. Regenerate to include it.)

## 3. D3e — CONTRACT.md content

Repo-root `CONTRACT.md`, prose-only, NO claim-creating wiki headings (it lives outside
`.codas/wiki`, so `extract_wiki_claims` ignores it anyway — only `doc_claims`/
`stale_claim` see its links; keep links to real paths). States: governed vs supporting,
the atlas:claims requirement + grammar, the verified-claim rule, the author workflow
(emit-pack / write / verify / never hand-edit generated pages).

## 4. Registration cascade (the dogfood-risk area)

Each edit is additive to an authoritative source; none is `spec_drift`-gated
(drift_couplings empty). Trace the policies each could trip:

| edit | risk traced |
|---|---|
| `structure.yml` add `wiki-contract` unit (path `CONTRACT.md`, owner, kind, purpose, canonical_placement) + repo-root allowed_children | `structure_drift`: path exists (we create CONTRACT.md) ✓; loader requires path/kind/owner/purpose/canonical_placement — include all. `missing_owner`: CONTRACT.md now matches the specific unit ✓ |
| `config.yml` add `CONTRACT.md` to supporting | `config_sources`: a declared source must exist ✓ |
| `documents.yml` add `wiki_contract` role (path, authority supporting, owner) | `document_set`: declared role path must exist ✓; not in `required_roles` (optional) |
| `AGENTS.md` pointer after `<!-- TRELLIS:END -->` | preserved region (line 19 says edits outside the block are kept); `doc_claims` link to `CONTRACT.md` exists ✓ |
| `.codas/wiki/index.md` pointer (link under a NON-canonical heading, e.g. `## Authoring`) | heading not in `_SECTION_KIND` → no `wiki_claims`; link → `doc_claim` → exists ✓. Do NOT add it under `## Canonical Sources` (would need config authority — it IS supporting now, so it would pass, but a contract is not a "canonical source"; keep it a plain pointer) |

CONTRACT.md is a NEW tracked file → enters inventory (doc_claims/units). `inventory
--json` stays deterministic (sorted facts) → byte-identical across processes; the
absolute hash changes once (new file) — expected.

Order of operations: create CONTRACT.md → edit structure/config/documents/AGENTS/index
→ `codas wiki --write` (regenerate governance.md, now includes the wiki-contract unit) →
`codas check .` = 0 → `codas wiki --verify` clean.

## 5. Tests

- `verify_generated_sections`: fresh repo (just written) → []; mutate the page on disk →
  the page is returned stale.
- `_generated_pages` deterministic; `write` then `verify` → [].
- CLI: `wiki --verify` exit 0 clean; exit 1 + lists when stale (temp fixture);
  `--verify --write` mutually exclusive → SystemExit 2.
- Real repo: `verify_generated_sections(cwd)` == [] (after regeneration);
  `run_check(cwd)` clean; CONTRACT.md exists + is owned (in inventory units or matched).

## 6. P5 completion

After the slice: `program.yml` work_item `program:P5:wiki-reconciliation` status
`in_progress` → `completed`; confirm its exit_criteria are met (wiki claims verified;
generated output grounded + verified; core stays deterministic + LLM-free). P6 becomes
unblocked. Update the deliverable notes (D3c/D3e shipped).

## 7. Open questions for review

1. Bundling D3c + D3e + P5-complete in one task — acceptable for closeout, or split?
   (Leaning bundle; both small, one codex review.)
2. `--verify` exit code: 1 on any stale (chosen, CI-friendly) vs 0-with-warning.
3. CONTRACT.md location: repo root (chosen, conventional + discoverable) vs `docs/`.
4. Regenerating governance.md adds a `wiki-contract` unit row + claim — confirm that is
   the only governance.md delta and it stays `generated_wiki_drift`-clean (the claim
   `unit: wiki-contract -> CONTRACT.md` matches the new structure unit).
5. Is adding a `wiki-contract` structure unit overkill vs leaving CONTRACT.md under the
   repo-root catch-all? (Leaning: register it — Codas should govern its own contract;
   and it makes the governance.md ownership panel complete.)
