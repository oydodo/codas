# Atlas Wiki Authoring Contract

The host-agent authoring contract for the Codas Atlas Wiki. This is the *schema* layer
of the wiki (raw repo + facts -> wiki -> **this contract**): the rules a coding agent
(or an OSS LLM-wiki backend) must follow when producing or editing Atlas content. Codas
**grounds** the wiki (verified facts), an LLM **renders** it, and Codas **verifies** it.

## What is governed vs supporting

- **Governed (verified):** the deterministic generated sections under
  `.codas/wiki/generated/**` and the `atlas:claims` blocks they carry. These are
  re-derivable from repository facts and are checked on every `codas check`.
- **Supporting (non-authoritative):** hand-authored concept pages under
  `.codas/wiki/concepts/**` and the wiki `index.md`. Prose orients agents and humans but
  **cannot out-rank repository facts or the authored claim sources** (`.codas/*.yml`,
  `docs/*.html`). A path or authority claim made in prose is still verified
  (`stale_wiki_claim` / `stale_claim`); unverifiable prose stays advisory.
- **Code-wiki (advisory prose + verified anchors):** hand-authored pages under
  `.codas/wiki/code/**` describe a module/concept (the semantic "flesh" facts lack; also an
  agent code-picture). Their **prose is advisory and NOT verified** — and is deliberately
  kept out of the byte-identical inventory hash (excluded from the doc/wiki claim scans).
  Only their `anchor_symbol` claims are verified by `code_anchor`, **warning-only** under
  open-world semantics. The `doc -> code` direction is not gated (a user-driven doc edit is
  followed by the agent, Trellis-style); the gate catches `code -> doc` drift (an anchored
  symbol renamed/moved without updating the page).

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
2. The verified surface is the fenced `atlas:claims` block, one anchor per line:
   - `anchor_symbol: <concept> -> <repo-rel path>:<symbol name>`
3. Each `anchor_symbol` **must resolve** to a current symbol fact (module + name). A
   non-resolving anchor is a `code_anchor` **warning** (never an error) — `symbols` is an
   open-world family, so absence is a lower bound, not proof: the code may have moved (update
   the page) or it may take a dynamic/conditional form the extractor misses.

## Author workflow

```bash
codas wiki --emit-pack    # ground: the verified facts to prefer over inferred structure
codas wiki --write        # (re)generate the deterministic sections
codas wiki --verify       # confirm committed generated pages match a fresh render (CI)
codas check .             # verify all claims (incl. generated_wiki_drift) — must be 0
```

`--emit-pack` is the grounding feed for a host agent or an OSS wiki backend; `--write`
renders the committed governance page; `--verify` (exit 1 if stale) is the CI freshness
gate; `codas check` enforces claim correctness on every run.
