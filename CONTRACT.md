# Atlas Wiki Authoring Contract

The host-agent authoring contract for the Codas Atlas Wiki. This is the *schema* layer
of the wiki (raw repo + facts -> wiki -> **this contract**): the rules a coding agent
(or an OSS LLM-wiki backend) must follow when producing or editing Atlas content. Codas
**grounds** the wiki (verified facts) and **renders** the generated pages + the `wiki/`
book DETERMINISTICALLY — no model; an LLM only **authors** the advisory source prose (kept
out of the byte-identical inventory hash), and Codas **verifies** the structural claims and
byte-compares the render. The reader-facing book at `wiki/` is itself a reserved derived
output (config `wiki.book_root`): excluded from every scan and resolved absent by every
claim/role existence check, so a doc that links it never feeds the hash the book pins.

## What is governed vs supporting

- **Governed (verified):** the deterministic generated sections under
  `.codas/wiki/generated/**` and the `atlas:claims` blocks they carry. These are
  re-derivable from repository facts and are checked on every `codas check`.
- **Supporting (non-authoritative):** hand-authored concept pages under
  `.codas/wiki/concepts/**` and the wiki `index.md`. Prose orients agents and humans but
  **cannot out-rank repository facts or the authored claim sources** (`.codas/*.yml`,
  `docs/*.html`). A path or authority claim made in prose is still verified
  (`stale_wiki_claim` / `stale_claim`); unverifiable prose stays advisory.
- **Code-wiki (advisory prose + verified structural claims):** hand-authored pages under
  `.codas/wiki/code/**` describe a module/concept (the semantic "flesh" facts lack; also an
  agent code-picture). Their **prose is advisory and NOT verified** — and is deliberately
  kept out of the byte-identical inventory hash (excluded from the doc/wiki claim scans).
  Only their `defines`/`calls`/`contains` structural claims are verified by `code_anchor`,
  **warning-only** under open-world semantics. The `doc -> code` direction is not gated (a
  user-driven doc edit is followed by the agent, Trellis-style); the gate catches `code -> doc`
  drift (a claimed symbol/edge renamed/moved without updating the page).

## Rules for generated pages

1. A generated page **must** embed a nonempty fenced `atlas:claims` block containing a
   `source_inventory_hash` line and at least one claim. An ungrounded generated page is
   a `generated_wiki_drift` **error**.
2. The `atlas:claims` grammar is line-oriented `key: subject -> value`:
   - `source_inventory_hash: sha256:<hex>` (exactly one; the freshness anchor)
   - `unit: <structure-unit-id> -> <path>`
   - `roadmap: <work-item-id> -> <status>`
3. **Every claim must be true against repository facts.** `generated_wiki_drift` verifies
   `unit:` against the Structure Map and `roadmap:` against the Program Plan; a claim the
   facts contradict is an **error**. An LLM may not assert what the facts do not support.
4. **Never hand-edit a generated page.** It is machine-rendered; edit the sources of
   truth (`.codas/structure.yml`, `.codas/program.yml`, the code) and regenerate.

## Rules for code-wiki pages (`.codas/wiki/code/**`)

1. The prose is **advisory** — write it for agents/humans, but Codas does not verify its
   meaning, and it must not enter the inventory hash (the scans skip this subtree).
2. The verified surface is the fenced `atlas:claims` block, one structural claim per line
   (node-id = `<path>::::<symbol>` for a top-level def, `<path>::<class>::<symbol>` for a
   method, or a bare repo-rel `<path>` for a module/package):
   - `defines: <concept> -> <node-id>`
   - `calls: <node-id> -> <node-id>`
   - `contains: <node-id>`
3. Each claim **must resolve** to a current fact (a `defines`/`contains` subject to a known
   node, a `calls` to a known call edge). A non-resolving claim is a `code_anchor` **warning**
   (never an error) — `symbols`/`calls` are open-world families, so absence is a lower bound,
   not proof: the code may have moved (update the page) or it may take a dynamic/conditional
   form the extractor misses.

## The W3 semantic judge loop (host-agent contract)

The semantic tier sits ABOVE the verified facts: the host agent writes the rich "what/why"
prose the facts cannot, Codas calibrates the agent's STRUCTURAL claims against facts, and the
agent judges grounded in those tiers. **Codas runs no model here (§17).** The loop:

1. **FEED** — `codas wiki --emit-feed` returns the verified knowledge tree + an instructions
   blob; this is the grounding the prose must stay anchored to. The tree is large — work **one
   subsystem (package) at a time**, never the whole repo at once.
2. **AUTHOR** — write prose pages under `.codas/cache/semantic/` (a gitignored, regenerable
   LOCAL cache — never committed, never in the inventory hash). Each page carries a fenced
   `atlas:claims` block of STRUCTURAL claims, one per line:
   - `defines: <concept> -> <node-id>`
   - `calls: <node-id> -> <node-id>`
   - `contains: <node-id>`
   where a node-id is the knowledge-tree address `path::<class-or-empty>::symbol` (the class
   segment is empty for a module-level def) or a bare repo-rel path for a module/package node.
3. **CALIBRATE** — `codas wiki --calibrate` tiers each structural claim against the facts,
   deterministically (offline JSON; **never** a `codas check` finding):
   - **STRUCTURE_CONFIRMED** — the cited tuple EXISTS. It does **NOT** confirm the `concept`
     prose; a structural match is necessary, never sufficient, for a semantic claim.
   - **UNCONFIRMED** — no match in an open-world family. Read as **UNKNOWN, never "false"**
     (absence is not denial — the node may take a form the static extractor misses).
   - **SEMANTIC** — a claim whose KIND names no fact family (a future capability/intent claim,
     NOT a `defines` with a capability-sounding concept); a pure hypothesis (reachable once
     capability-claim kinds land; v0 has none).
4. **JUDGE** — the host agent reasons over (facts + tree + tiers) and emits semantic-legality
   SUGGESTIONS, under the iron rules:
   - **Trust STRUCTURE_CONFIRMED structure, never its concept.** Verify the concept by reading;
     if it contradicts the code, FLAG it — a confirmed tuple never launders a false concept.
   - **ABSTAIN on UNCONFIRMED.** Do not assert the thing is absent; suggest re-checking the node-id.
   - **Never upgrade** a SEMANTIC or UNCONFIRMED claim to trusted.
   - Output is **suggestion-only, never committed** — it cannot become a fact or a `codas check`
     verdict (that would break byte-identity and §17).

### Delegate the LLM steps to a cheap sub-agent

Only AUTHOR and JUDGE use a model; FEED and CALIBRATE are deterministic Codas calls. So the
"host agent" need not be your expensive main agent — dispatch AUTHOR + JUDGE to a **cheap,
disposable sub-agent**, while the main agent runs only `--emit-feed` / `--calibrate` and merges
the suggestion-only output. The bulky feed and the prose reasoning then never pollute the main
context, the cost lands on a weak model, and N sub-agents can run one-package-each in parallel.

This is safe on a weak model **because of** the calibration, not despite it: a hallucinated
node-id tiers to UNCONFIRMED, and a false concept on a real tuple stays STRUCTURE_CONFIRMED with
the concept unverified — so a cheap model cannot launder a false claim past the iron rules above.
Fact-anchoring substitutes for model capability; cheap-but-disciplined beats
expensive-but-ungrounded. Codas spawns nothing — the dispatch is the harness's job (Codas core
shells only deterministic tools, never a model).

### Worked example (dogfooded on the calibration layer itself)

A page under `.codas/cache/semantic/` describing the W3 calibrator carries:

```atlas:claims
defines: assigns the deterministic trust tier -> src/codas/app/calibrate.py::::tier
contains: src/codas/app/calibrate.py::::build_feed
calls: src/codas/app/calibrate.py::::calibrate -> src/codas/app/wiki.py::::build_atlas_tree
calls: src/codas/app/calibrate.py::::tier -> src/codas/app/calibrate.py::::_absent
defines: implements a neural ranking model -> src/codas/app/calibrate.py::::tier
contains: src/codas/app/calibrate.py::::nonexistent_helper
```

`codas wiki --calibrate` tiers them — the structurally-real ones STRUCTURE_CONFIRMED, the absent
node UNCONFIRMED. **Judge verdict (the discipline in action):**

- The real `defines`/`contains`/`calls` tuples are STRUCTURE_CONFIRMED; their concepts read as
  correct, but Codas confirmed only that the tuples EXIST — the prose stays the agent's, advisory.
- "`tier` implements a neural ranking model" is **also** STRUCTURE_CONFIRMED, because `tier`
  exists. That does **not** mean `tier` is a neural model — reading the code, it is a
  deterministic dict-lookup, so the concept is false. The judge FLAGS it: a confirmed tuple never
  validates a wrong concept (the laundering defense, demonstrated).
- `nonexistent_helper` is UNCONFIRMED. The judge does **not** declare it nonexistent (open-world);
  it suggests re-checking the node-id.

The value: the agent gets the rich semantic layer, yet every structural claim is fact-anchored and
no LLM assertion can masquerade as ground truth.

## Verification contract

Every wiki artifact falls into one of four classes; each has a defined verifier and a defined
relationship to the byte-identical inventory hash. Nothing an LLM writes is trusted on faith —
it is either re-derivable, structurally fact-checked, or explicitly advisory.

| Class | Where | In the hash? | Verifier |
|---|---|---|---|
| **FEED** (grounding) | `--emit-pack`/`--emit-tree`/`--emit-feed` stdout | no (ephemeral) | n/a — derived on demand |
| **GENERATED** (governance pages) | `.codas/wiki/generated/**` | yes (committed facts) | `generated_wiki_drift` (claims) + `codas wiki --verify` (byte-compare) |
| **WIKI-PAGES** (concept + code prose) | `.codas/wiki/**` incl. `.codas/wiki/code/**` | prose **out**; structural claims verified | `stale_wiki_claim` / `code_anchor` |
| **CACHE** (offline semantic corpus) | `.codas/cache/semantic/**` | no (gitignored) | `codas wiki --calibrate` (offline only) |
| **BOOK** (reader-facing) | `wiki/` (config `wiki.book_root`) | no (reserved derived output) | `codas wiki --verify` (byte-compare) |

Verifier routing — which policy owns each claim stream (a claim is reported by exactly one,
so the `stale_*` policies never double-count):

| Claim stream | Source | Policy |
|---|---|---|
| markdown path/link refs | governance `.md` | `stale_claim` |
| HTML path/link refs | authoritative/supporting `.html` | `stale_html_claim` |
| wiki structural refs (`canonical_source` / `concept_page` / `evidence` / `sync_target`) | `.codas/wiki/**` pages | `stale_wiki_claim` |
| generated `atlas:claims` (`unit` / `roadmap` / `source_inventory_hash`) | `.codas/wiki/generated/**` | `generated_wiki_drift` |
| code-wiki structural claims (`defines` / `calls` / `contains`) | `.codas/wiki/code/**` | `code_anchor` (warning-only, open-world) |
| the rendered book | `wiki/` | `codas wiki --verify` (not a `codas check` policy) |

The book is verified by RE-RENDER, never by re-scan: `--write` regenerates it deterministically
and `--verify` byte-compares the committed bytes to a fresh render (exit 1 if stale, incl. an
orphaned chapter). It carries no `atlas:claims` block and is never an input — its freshness is
purely "do the committed bytes equal what the facts render today".

## Author workflow

```bash
codas wiki --emit-pack    # ground: the verified facts to prefer over inferred structure
codas wiki --emit-tree    # the neutral knowledge tree (package -> module -> class -> function)
codas wiki --emit-feed    # the W3 grounding feed (tree + judge instructions) for a host agent
codas wiki --calibrate    # tier the offline semantic corpus against facts (offline JSON)
codas wiki --emit-mermaid # a Mermaid dependency graph (deterministic, with the open-world note)
codas wiki --emit-html    # a self-contained static HTML view (no external script)
codas wiki --write        # (re)generate the deterministic governance sections
codas wiki --verify       # confirm committed generated pages match a fresh render (CI)
codas check .             # verify all claims (incl. generated_wiki_drift) — must be 0
```

`--emit-pack` / `--emit-tree` / `--emit-feed` are grounding feeds for a host agent or an OSS wiki
backend; `--calibrate` runs the W3 semantic loop above; `--emit-mermaid` / `--emit-html` are
deterministic views; `--write` renders the committed governance page; `--verify` (exit 1 if stale)
is the CI freshness gate; `codas check` enforces claim correctness on every run.
