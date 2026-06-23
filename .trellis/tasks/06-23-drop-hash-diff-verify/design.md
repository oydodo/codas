# Design — drop-hash + unified diff verification

Status: DRAFT for codex DESIGN review (gate-semantics → review before impl).
Grounded in a read of the actual code at `main@61182eb`. **The PRD framing had two
inaccuracies; this design corrects them (§1) and re-scopes accordingly (§3).**

## 1. Corrected current-state (what the code ACTUALLY does)

Read of `core/provenance.py`, `app/wiki.py`, `app/book.py`, `policies/generated_wiki_drift.py`,
`facts/context.py`:

| claim in PRD | reality in code |
| --- | --- |
| "verify by re-render+byte-compare like the book does" (future) | **byte-compare ALREADY exists** for BOTH committed derived artifacts. `codas wiki --verify` = `verify_generated_sections(repo) + verify_book(repo)` (cli.py:413-416); each = re-render + `read_bytes() != content` (wiki.py:500-512, book.py:295-303). |
| generated page pins a whole-inventory hash | page hash is **already narrowed** to the exact rendered fields `{units[id,path,kind,owner], roadmap[id,phase,status]}` (wiki.py:473-479), NOT whole-inventory. The whole-inventory hash survives only on the **emit-only** pack/tree (wiki.py:172/376), which are `--emit-pack`/`--emit-tree` → stdout, **never committed, never verified**. |
| `generated_wiki_drift` (the always-on gate) checks freshness by hash | gate **deliberately does NOT check freshness** (docstring 32-37). It checks (i) structural: page carries a nonempty `atlas:claims` block WITH a `source_inventory_hash` + ≥1 claim; (ii) fact-consistency: each `unit:`/`roadmap:` claim matches structure.yml / program.yml. Freshness was kept OUT of the gate because the OLD whole-inventory hash churned. |

**Net:** the byte-compare migration the PRD asks for is, for the committed artifacts, **already
shipped**. What remains is genuinely smaller and is about removing a now-redundant hash and
nailing down where freshness authority lives.

## 2. Two facts that change the scope

1. **The generated-page `source_inventory_hash` is now redundant.** `verify_generated_sections`
   re-renders the WHOLE page (incl. the claim block) and byte-compares. The page's rendered
   `unit:`/`roadmap:` claims already track the exact same fields the narrowed hash pins, so the
   hash line catches nothing the byte-compare doesn't already catch. It is a redundant freshness
   anchor layered over content that already moves with the same facts.
2. **The always-on gate cannot host the byte-compare without a re-scan.** `ScanContext` exposes
   facts (symbols/imports/calls/claims) but **no pre-built inventory dict and no render**
   (facts/context.py). Re-rendering needs `run_inventory(repo, exclude_under=...)` — a second
   full scan inside a policy, which violates the ScanContext-only discipline (§11) and doubles
   scan cost. So freshness byte-compare must stay in `codas wiki --verify` (which already
   re-renders), NOT move into per-commit `check`.

## 3. Design (re-scoped, minimal, correct)

### 3a. Drop the redundant generated-page hash
- `render_generated_overview` (wiki.py:385): remove the `source_inventory_hash` parameter and
  the `f"source_inventory_hash: {hash}"` line (445). Claims block keeps the `unit:`/`roadmap:`
  lines.
- `_generated_pages` (wiki.py:456): delete the `rendered_source` + `source_hash` computation
  (473-479); call `render_generated_overview(inventory)`.
- `generated_wiki_drift` (policy): drop the structural requirement that the page carry a
  `source_inventory_hash` (line 53 `page.source_inventory_hash`). Keep "nonempty claims block
  + ≥1 claim". Keep both fact-consistency checks.
- generated-claims parser (`adapters/...extract_generated_claims`): drop or tolerate the
  `source_inventory_hash` field; `GeneratedPage.source_inventory_hash` removed from the gate
  predicate. (Keep parser backward-tolerant so an old committed page with the line still parses
  — the byte-compare will rewrite it on next `--write`.)
- **Freshness loss: none.** `verify_generated_sections` byte-compare fully covers it.

### 3b. Pack/tree whole-inventory hash → explicitly audit-only
- `build_atlas_pack` (172) / `build_atlas_tree` (376) keep `inventory_hash(...)` as an
  **emit-time provenance receipt** on an ephemeral, recomputed-each-emit artifact (never stale,
  never a gate). Document the reclassification in `provenance.py` docstring: `inventory_hash` is
  an audit/provenance stamp, NOT a freshness mechanism. (PRD decision (a): KEEP, audit-only.)

### 3c. Freshness authority = `codas wiki --verify` (+ CI), NOT the per-commit gate
- Document (provenance + generated_wiki_drift docstrings): all committed derived artifacts
  (governance page + `wiki/` book) verify by re-render+byte-compare via `--verify`; the gate
  keeps the cheap fact-consistency claim checks; freshness is `--verify`/CI because the gate
  cannot re-render without a re-scan (§2.2).
- **Corrects PRD decision (b):** the PRD said "byte-compare per-commit (gated, current)". The
  code shows freshness is `--verify`-only, never gated, and CANNOT be gated cheaply. So the
  resolution is `--verify`/CI, not "keep gated". (If per-commit freshness is later wanted, it
  needs an inventory-dict-on-ScanContext seam — out of scope here, note as follow-up.)

### 3d. Determinism = run-twice test (kept)
- Canonical serialization (`render_inventory_json`, sort_keys) stays. Add/confirm a run-twice
  determinism test: build inventory twice → identical bytes. `inventory_hash` is retained for
  this test + the emit receipt (3b), never as a committed-artifact freshness gate.

## 4. Concrete deltas (FULL surface — codex-verified `grep source_inventory_hash`)

The change footprint is THREE-way. Dropping the page hash is NOT just code — the page-hash
requirement is DOCUMENTED in governed text (policy spec + program plan + contract + 2 HTML
design docs); those must co-change in the same diff or `stale_html_claim` / `stale_claim` /
`fact_coupling` fire. The pack/tree audit hash is UNTOUCHED.

### 4a. DROP surface (the page hash)
| file | change |
| --- | --- |
| `app/wiki.py:386,392,445,460,504` | drop `source_inventory_hash` param+line in `render_generated_overview`; drop `source_hash` calc (`_generated_pages` 473-479); fix docstrings |
| `adapters/wiki.py:220,239,273,295` | drop `GeneratedPage.source_inventory_hash` field + its parse; OR keep tolerant (parse-but-ignore) so an old committed page still loads then rewrites clean |
| `policies/generated_wiki_drift.py:26,32,53,60` | structural predicate `has_block and source_inventory_hash and claims` → `has_block and claims`; fix docstring |
| `facts/context.py:224` | docstring mention only |
| `.codas/wiki/generated/governance.md:53` | regenerate via `codas wiki --write` (drops line 53) |
| tests | `test_generated_wiki_drift.py:42,92,129,136,143,156,164`; `test_generated_sections.py:37,70,87,92` — drop hash-present/missing-hash assertions; add run-twice determinism test + regression (field change → `--verify` catches; old page with hash line still parses + rewrites clean) |

### 4b. DOC co-change (governed text describing the page-hash requirement — MUST update)
| file | what it says today |
| --- | --- |
| `.codas/policies.yml:70` | policy description: "must embed … with a source_inventory_hash" |
| `.codas/program.yml:143,144,145` | D3a/b/c/d narrative names source_inventory_hash repeatedly |
| `CONTRACT.md:35,38,163` | authoring contract: "source_inventory_hash line … the freshness anchor" + routing table row |
| `docs/codas-design.html:1127` | 生成页 atlas:claims 块携带 … source_inventory_hash |
| `docs/codas-implementation-plan.html:627,750,756,876,1095` | describes the page carrying source_inventory_hash |

### 4c. KEEP — pack/tree audit hash (NOT dropping; reclassify docstring only)
| file | note |
| --- | --- |
| `app/wiki.py:63,166,172,252,371,376` | pack/tree emit hash STAYS (audit receipt) |
| `app/calibrate.py:119`, `structure/inventory.py:55` | docstrings ref pack/tree hash — leave |
| `core/provenance.py` | docstring: `inventory_hash` = audit/provenance receipt, not committed-artifact freshness |
| `test_atlas_pack.py`, `test_knowledge_tree.py` | pack/tree hash tests UNCHANGED |

## 7. codex DESIGN review outcome (a485f85e, 2026-06-23)

**Verdict: APPROVE-WITH-CHANGES.** §1 current-state table confirmed accurate (A-E all verified
against source). Runtime design is correct: byte-compare already exists (wiki.py:509-512,
book.py:299-303, cli.py:413-416); page hash redundant; gate can't re-render (ScanContext has no
inventory dict, context.py:95-99); freshness rightly stays in `--verify`/CI.

**BLOCKERS folded into §4b above** (the doc co-change surface I missed): `.codas/policies.yml`,
`.codas/program.yml`, `CONTRACT.md`, `docs/codas-design.html`, `docs/codas-implementation-plan.html`,
+ the 4 test locations. **codex FALSE POSITIVE**: it listed `app/agents_block.py:44-45` as
emitting the hash — `grep` shows ZERO `source_inventory_hash` in agents_block.py; dropped.

**§6 answers (codex-adjudicated):** Q1 no external consumer of the embedded line (only the
policy reads it). Q2 `--verify`/CI is the right home (gate re-render needs a re-scan). Q3 keep
pack/tree hash as-is (audit-only). Q4 no runtime dogfooding trap; the only trap is governed-doc
drift → §4b handles it.

## 5. Compatibility / rollout
- Byte-identical invariant preserved: the page render loses a line → its committed bytes change
  ONCE (regenerate via `codas wiki --write`), then stable. Re-run `--write` in the same commit.
- `codas check .` stays 0 findings; `--verify` clean after regenerate.
- No config/schema migration; no public CLI change.

## 6. Open questions for codex DESIGN review
1. Is dropping the page `source_inventory_hash` entirely correct, or is there a consumer of that
   embedded line outside `generated_wiki_drift` (e.g. an external tool reading the claims block)
   that still needs a provenance stamp in the committed page?
2. Should `generated_wiki_drift` ALSO gain a byte-compare (accepting a re-scan or a new
   inventory-on-ScanContext seam), making the gate catch freshness per-commit — or is
   `--verify`/CI the right home? (This design says `--verify`/CI; challenge it.)
3. Pack/tree: keep the whole-inventory emit hash, or narrow it to the projected fields for
   consistency with the (now-removed) page approach? (This design says keep as-is, audit-only.)
4. Any byte-identical / dogfooding-protocol trap in regenerating the committed governance page
   within this task's own commit?
