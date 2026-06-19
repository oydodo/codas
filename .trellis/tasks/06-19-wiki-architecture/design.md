# Design — Codas Wiki Architecture (verified, agent-driven LLM-wiki)

Authority: plan §1 (wiki/MCP/CI are delivery channels), §2/§2.1 (wiki is not the
truth source; a wiki claim becomes a governance fact only when Codas verifies its
evidence + authority; Orientation Layer), §11 (adapter boundary; core receives only
normalized facts/claims), §17 (no LLM for correctness; wiki follows inventory), §8
(P5 wiki, P6 enforcement, P7 MCP + Role Integrations). Decision provenance: a 3-lens
design workflow + two codex adversarial rounds + a grill session.

## 0. Purpose & audience — Atlas is a live governance map, not post-hoc docs

Codas's wiki (Atlas) is **not** a CodeWiki/DeepWiki-style documentation generator,
and the difference is purpose + temporality, not just rendering:

| | CodeWiki / DeepWiki | Codas Atlas |
|---|---|---|
| Temporality | maps an **already-built** repo (post-hoc) | maps a repo **being / yet to be built** (in-flight) |
| Audience | **humans** (understand the project) | **agents + humans** (guide agent work + control deviation) |
| Nature | **descriptive** (what the code is) | **prescriptive + verified** (what the code *should* be + whether it drifted) |
| Direction | backward (record what is) | forward (steer what's being built) |
| Refresh | occasional regenerate (snapshot) | continuously verified every `codas check` (live) |
| Core question | "how does this project work?" | "what do I touch / can I depend on? am I drifting from the plan?" |

Consequence: an LLM prose doc-site (CodeWiki-style) is an **optional, P7,
human-onboarding adjunct** — not the product. The product is the **deterministic,
prescriptive, drift-controlling Atlas**, which needs no LLM. Much of it already
exists: preflight (P4) = agent guidance, the policy engine = deviation control,
program.yml = plan progress. **Atlas = a readable rendering of that live governance
state**, for an agent about to work and a human supervising drift.

This re-weights the **generated sections** (D3b) toward governance panels over a
static code dump:
1. **intended vs actual** — structure.yml's ownership/dependency intent vs observed
   (a visualization of `structure_drift` / `dependency_direction`); deviation control.
2. **plan progress** — program.yml phases + where we are; human progress tracking.
3. **open deviations** — live findings + waivers; deviation control.
4. **placement guidance** — where new code goes, what it may depend on, who owns it
   (preflight-style); agent guidance.
5. (supporting) dependency graph / symbol index — the descriptive layer underneath.

The CodeWiki/DeepWiki integration (§6) consumes these same verified facts only to
produce the *optional human-prose adjunct*; it does not define Atlas's purpose.

## 1. The architecture — four layers, one LLM boundary

| Layer | What | Where | LLM? | Determinism |
|---|---|---|---|---|
| 1. Facts core | inventory facts (imports/symbols/units/wiki_claims/program), ScanContext seam, provenance hash | `src/codas/{core,structure,facts}` | No | byte-identical |
| 2. Atlas export ("FEED") | grounding pack projected from inventory; deterministic generated sections | `src/codas/app/wiki.py` (adapter-normalized, LLM-free) | No | byte-identical |
| 3. Verification ("VERIFY") | lints generated output back against facts → `codas check` findings | `src/codas/policies/{stale_wiki_claim, generated_wiki_drift}.py` via ScanContext | No | deterministic |
| — **§17 LLM boundary** — | | | | |
| 4. Generation | host agent reads pack+contract, writes pages (itself, or drives an OSS tool) | the host agent / an external orchestrator | Yes | non-deterministic, never on check path |
| 5. Backend wiring (P7) | per-OSS-tool injection adapters (push grounding into the tool) | `src/codas/integrations/` | No (in-repo) | n/a |

Codas owns layers 1–3 (deterministic, no LLM) and the layer-5 *contract*. The LLM
lives only in layer 4 (the host agent), out of Codas's process. `codas check`,
`inventory`, and the policy engine never cross the §17 line.

## 2. Atlas ≅ LLM-wiki (one wiki, two renderings — naming)

Codas's wiki is the **same three-layer architecture as Karpathy's "LLM Wiki"**, which
dissolves the apparent split with mainstream LLM-wikis:

| Karpathy LLM-wiki | Codas |
|---|---|
| `raw/` immutable verification baseline | repo + facts (inventory) |
| `wiki/` interlinked markdown | `.codas/wiki/` |
| `schema` (CLAUDE.md maintenance rules) | `AGENTS.md` + `CONTRACT.md` |
| Lint workflow (contradictions/stale/orphans) | `stale_wiki_claim` + `generated_wiki_drift` (deterministic, enforced) |

The only essential difference is the **engine**: mainstream LLM-wikis use an LLM to
author + lint with judgment; Codas verifies + generates deterministically, and the
LLM is the *host agent*, not embedded. Frame to users as **"Atlas grounds it, an LLM
renders it, Atlas verifies it"** — one wiki, two render targets (hand-authored
concept pages + a generated view), both held to the same deterministic facts. Avoid
"Atlas vs LLM-wiki" framing.

## 3. Chain-of-trust — a constraint per link

The discovery → injection → verification chain. The governing principle: **process
can't be enforced; artifacts can.** Each link's guarantee is an artifact requirement
verifiable at `codas check`, gated by a P6 hook.

```
human setup → AGENTS.md (schema) → agent reads → codas wiki --emit-pack (ground)
   → agent writes / drives OSS tool → codas check (verify) → P6 hook (gate)
```

| Link | Silent-failure mode | Constraint (artifact, check-verifiable) | Lands in |
|---|---|---|---|
| ① human setup | not installed / no hook / no AGENTS.md Codas section | `codas doctor` setup-completeness check (hook installed? schema section present? wiki config present?) + the P0 bootstrap self-check | `doctor` (de-stub), bootstrap |
| ② AGENTS.md schema | absent / drifted / references a dead command | schema is a governed doc (documents.yml + structure.yml); `stale_claim` verifies its links; **new contract-check**: the `codas wiki` subcommands it names must exist and it must point at a real `CONTRACT.md`; Codas regenerates the section via `--write` | D2 + a small contract check |
| ③ agent grounds | agent ignores AGENTS.md, writes ungrounded prose | enforce the **output**, not the reading: a page under `.codas/wiki/generated/**` must embed `source_inventory_hash` + a nonempty `atlas:claims` block; missing → `generated_wiki_drift` finding | D3d |
| ④ generation | content wrong / hallucinated / cherry-picked | `generated_wiki_drift` (fact-consistency, bogus claim = **error**) + `stale_wiki_claim` (existence/authority) | D3d / D2 |
| ⑤ check runs + gates | nobody runs check / findings ignored | P6 hook gates on `codas check` (pre-commit local + CI server-side, unbypassable by `--no-verify`); `doctor` asserts the hook is installed | P6 hook + doctor |

**Honest boundary.** Hand-authored concept pages (human *intent*) are NOT required to
carry a grounding block — they are verified by `stale_wiki_claim` for any path /
authority claim they make, and pure prose stays supporting-tier (§2: cannot out-rank
facts). The grounding-proof requirement (`atlas:claims` + hash) applies to the
**generated** directory only. An agent dumping hallucinated prose as a "concept page"
gains nothing: its checkable claims are still verified, and its unverifiable prose is
non-authoritative by construction.

## 4. Verification design

Two policies, both adapter-normalized via ScanContext, both wired into `app/check.py`
+ `policies.yml`.

### `stale_wiki_claim` (shipped, D2) — existence + authority
Owns: a literal `canonical_source` must be a declared constraint source (glob-aware);
`canonical_source`/`evidence`/`sync_target` code-span paths must exist. Severity
warning. Runs over any wiki page in the authored grammar.

### `generated_wiki_drift` (new, D3d) — fact-consistency + freshness
Scope: pages under `.codas/wiki/generated/**`. A **real `atlas:claims` block parser**
(NOT the existing wiki adapter — codex confirmed the adapter skips fenced blocks and
only extracts under recognized headings, so it will not verify a claims block "for
free"). Required: each generated page must carry a nonempty `atlas:claims` block + a
`source_inventory_hash` marker. Checks each claim against the fact tables it was
generated from:
- `depends_on: A -> B` vs `ctx.imports()` (unit/module edges)
- `symbol: name @ path` vs `ctx.symbols()`
- `owner: unit = X` vs structure units
- freshness: embedded `source_inventory_hash` vs the current source hash

Severity split (informed by P6 hooks, which gate on errors by default):
- **error**: a claim the facts contradict (a hallucinated/false assertion) — a
  verifiable lie must block.
- **warning**: stale `source_inventory_hash` (code changed, page not regenerated) —
  prompts `codas wiki --write`, not a hard block.

### `source_inventory_hash` — the hash-loop fix (codex BLOCKER)
A committed generated page that embeds the *full* `inventory_hash` is self-referential:
the inventory ingests `.codas/wiki/`, so the page's own bytes feed the hash it embeds
→ the hash chases itself. Fix: `source_inventory_hash` = the inventory hash computed
over an inventory that **excludes `.codas/wiki/generated/**`**. Generated pages embed
that; `generated_wiki_drift` checks against that. Editing/regenerating the pages then
does not move the hash they pin to; only changes to the *source* (code/facts) do.

Required golden fixtures (the §17 guardrails): bogus dependency claim → error finding;
missing `atlas:claims` block → finding; stale `source_inventory_hash` → warning.

## 5. The grounding pack + generated sections

### Pack (D3a) — a derived view, not a persisted truth source
`build_atlas_pack(repo)` projects `run_inventory(repo)` (one scan, adapter-normalized
like `app/preflight.py`) into: `dependency_graph` (from import facts), `symbol_index`
(symbol facts, scoped to `src/codas`), `ownership` (units), `concept_index`
(wiki_claims), `roadmap` (program), `verified_evidence` (wiki_claims, exists=true),
+ `source_inventory_hash`. Deterministic (`json.dumps(sort_keys=True)`, no timestamp).
Emitted to **stdout** (`codas wiki --emit-pack`); also emittable as `llms.txt` /
`AGENTS.md` / a repomix-shaped pack for OSS-tool consumption. NOT committed (a
committed pack would be a second source of truth that drifts; test `pack ==
project(inventory)` enforces the derived-view invariant). Lead with a `VERIFIED
GOVERNANCE FACTS (prefer over inferred structure)` preamble so an LLM weights it.

### Generated sections (D3b) — committed, guarded
Deterministic markdown renderers (no LLM): dependency graph (Mermaid), symbol index,
structure units, roadmap → `.codas/wiki/generated/*.md`, each embedding the
`source_inventory_hash` marker + an `atlas:claims` block. **Committed** (so
`generated_wiki_drift` dogfoods their freshness; gitignored files are dropped by
`--exclude-standard` and would not be checked at all). The deterministic sections are
both human/agent-readable today (no LLM needed) and grounding material for the LLM
render step.

## 6. OSS-tool compatibility & injection (no MCP)

The OSS tool never needs to know Codas exists; the **Codas-aware orchestrator (agent
or CI) bridges** them. Mechanisms, passive → active:

- **A. Repo-resident convention files** (passive): Codas writes `llms.txt` /
  `AGENTS.md` / a grounding doc the tool already ingests via RAG. Zero integration.
- **B. Generic instruction knob** (semi-active): the tool's own
  `--instruction-file` / custom-prompt / rules input is pointed at Codas's pack.
- **C. Subprocess wrap** (active): `codas wiki --backend X` drives the tool, injecting
  the pack as context + pre-seeding its config. Per-backend adapter.
- **D. Agent-driven** (primary): the host agent runs `codas wiki --emit-pack`, then
  writes pages or drives the tool, then `codas check`. The agent is the Codas-aware
  party.

### Per-backend injection points (research `a6f4d07`, source-verified)

| Tool | Re-derives structure? | Codas injection (no fork) | Adapter emits |
|---|---|---|---|
| **CodeWiki** (#1, recommended first target) | tree-sitter + networkx dep/call graph + LLM clustering | **pre-write `first_module_tree.json`** → CodeWiki loads it and SKIPS its LLM clustering (`if os.path.exists(first_module_tree_path): load + skip`); `--instructions "<pack>"` → lands in every module-agent's `{custom_instructions}` prompt slot. NB its emitted dep-graph JSON is write-only/ignored — do NOT inject there; deep per-edge correction = wrap `build_dependency_graph()` to return Codas `Node` objects | `first_module_tree.json` (CodeWiki module-tree schema) + an `--instructions` blob |
| **deepwiki-open** (#2) | LLM derives wiki *structure* from file-tree + README (no AST/dep-graph) | write a **verified `README.md`** that becomes the structure-derivation input (replaces inferred structure); or a facts `.md` surviving `repo.json` filters (FAISS retrieves into page bodies); self-host: patch `/local_repo/structure` or `POST /api/wiki_cache` to bypass its LLM | grounding `README.md` (+ optional `wiki_cache` JSON) |
| **autodoc** (#3) | none (pure LLM summarization) | write `CODAS_GROUNDING.txt` in root (avoid `.md`/dotfiles/`*test*` — default-ignored) + a `filePrompt`/`folderPrompt` "prefer verified facts" preamble | plain-text pack + prompt-preamble strings |

**Confirmed**: the "Codas replaces the derivation step" hypothesis holds strongest for
CodeWiki (file-based `first_module_tree.json` substitution, no fork — the most literal
"verified facts replace inferred structure"). deepwiki-open is partial (replace the
structure-derivation README input). autodoc has nothing to replace (additive only).
All three consume Codas's existing emit formats (json / markdown / llms.txt /
repomix-shaped) with only per-adapter schema-shaping; **none requires MCP**.

Recommended first backend = **CodeWiki** (highest correction leverage + cleanest
file-based seam). Backend adapters live in `src/codas/integrations/` and are **P7**;
P5 only ships the format-neutral grounding pack + verification.

Backend adapters (C) are **P7** (`integrations/`); P5 ships only the standard-format
emit (A/B inputs) + verification. A default backend is **not** chosen now.

## 7. Enforcement (soft → hard)

| Layer | Mechanism | Strength | Bypass | Phase |
|---|---|---|---|---|
| convention | AGENTS.md instructs the agent | soft | agent ignores | P5 (contract) |
| local hook | pre-commit/pre-push runs `codas check`, blocks on findings | medium | `git commit --no-verify` | P6 |
| server gate | GitHub Action / required check; red PR can't merge | hard | none | P6 |

The wiki is enforced **for free** by the generic hook: the hook gates on `codas
check`, and the wiki policies (`stale_wiki_claim`, `generated_wiki_drift`) are already
in `check`. No wiki-specific hook code. The hook also removes reliance on the agent
reading AGENTS.md (installed once by `codas init`, then auto-runs).

## 8. P5 D3 slice plan (deterministic spine; no LLM, no MCP)

- **D3a — pack.** `app/wiki.py::build_atlas_pack` (inventory projection + `source_inventory_hash`); `codas wiki --emit-pack` (stdout) + `--emit llms.txt`. Test `pack == project(inventory)`.
- **D3b — generated sections.** Deterministic renderers → committed `.codas/wiki/generated/*.md` with `source_inventory_hash` + `atlas:claims` blocks. Idempotent (write twice byte-identical).
- **D3c — command.** `codas wiki` in `cli.py` + `app/wiki.py`: `--emit-pack` / `--write` / `--verify`. De-stub.
- **D3d — verification.** `generated_wiki_drift` policy (real `atlas:claims` parser, fact-consistency, `source_inventory_hash` freshness; bogus=error, stale=warning); register in check.py + policies.yml; golden fixtures.
- **D3e — contract + schema layer.** `CONTRACT.md` (committed, in `docs/` or repo root — NOT inside the Trellis-managed AGENTS.md block) stating only `atlas:claims` + deterministic sections are governed and prose is non-authoritative; a short AGENTS.md pointer outside the managed block; register the doc.

Each slice keeps `codas check . = 0`, `inventory --json` byte-identical, `unowned`
empty, and runs the固化节奏 (prd + design + codex review + tests).

## 9. Phasing

| Phase | Ships |
|---|---|
| P5 (now) | deterministic spine: pack, generated sections, `codas wiki` command, both verification policies, contract/schema layer. No LLM. No MCP. |
| P6 | enforcement hooks (pre-commit/pre-push/GitHub Action) gating `codas check` — wiki enforced for free; `codas init`/`doctor` scaffold + diagnose. |
| P7 | per-backend OSS injection adapters (`integrations/`, default backend chosen here); host-agent-specific behavior. No MCP. |

## 10. Deferred / open

- Default OSS backend choice + per-backend adapter shapes — P7, pending `a6f4d07`.
- `codas doctor` / `codas init` implementation (setup + chain links ① and ⑤) — P5/P6.
- `--brief` (self-contained generation instruction bundle) — P5 D3c or a fast-follow.
- The contract-check for link ② (named subcommands exist) — small, D3e or P6.
