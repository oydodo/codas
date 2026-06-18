# PRD — P5 D1: wiki claim parser

## Context

P5 (`program:P5:wiki-reconciliation`) deliverables: "Wiki claim parser",
"Generated wiki sections", "Stale wiki claim policy"; exit "Wiki claims are
verified against repo facts." This slice ships the **wiki claim parser** — the
facts foundation the D2 `stale_wiki_claim` policy and D3 `codas wiki` command
build on.

**Authority.** Plan §2: "Wiki is not the truth source. Wiki is a readable summary
and claim surface. A wiki claim becomes a governance fact only when Codas can
verify its evidence **and authority**." §2.1 Orientation row: "Wiki and indexes
help navigation; they do not become fact sources by themselves." §5 Wiki module:
inputs `inventory, concept index, wiki files`; outputs `wiki pages, stale wiki
findings`. §6 Core Data Contract gives the canonical wiki-claim shape
(`claim:wiki:<slug>` with `kind` + `evidence:[{path}]`). §17: "Wiki must follow
inventory, not precede it" — so the parser emits *facts into the inventory*, it
does not generate pages (that is D3).

The repo wiki today (`.codas/wiki/`): `index.md` (a `## Canonical Sources`
backtick-path list + a `## Concepts` link list + a Bootstrap code block) and three
concept pages (`codas-product`, `repository-structure`, `trellis-task-system`),
each with `Evidence:` backtick-path lists and a `## Required Synchronization`
path list. `config.yml` declares `wiki: {enabled: true, path: .codas/wiki,
require_evidence: true}`.

## Goal

Add a deterministic **wiki claim** fact: parse the structured path assertions a
wiki page makes — grouped by the wiki's *intent* (which concept asserts it, and as
what kind: a canonical source, a concept-page link, an evidence pointer, or a
required-sync target) — and surface them in `codas inventory` and through the
`ScanContext` seam, so the D2 policy can verify each against repo facts without
importing an adapter. Facts-only: zero new findings, `codas check . = 0`.

## Why not just reuse `doc_claims`

`doc_claims` (and the `stale_claim` policy) already index *every* markdown link /
code-span path and flag broken ones. A wiki claim is **narrower and semantic**: it
is a path reference the wiki makes *in a structural role* (`canonical_source`,
`concept_page`, `evidence`, `sync_target`) that D2 verifies against a *non-filesystem*
authored fact (config authority, structure units, documents manifest) — not mere
file existence. Keeping wiki claims a distinct fact block lets D2 check authority
and concept consistency while leaving raw path existence to `stale_claim` (no
double-finding).

## Requirements

1. New adapter `src/codas/adapters/wiki.py`:
   - `@dataclass(frozen=True) WikiClaim`: `source` (repo-rel wiki `.md` path),
     `line`, `concept` (slug from filename; `index` for the wiki index), `kind`
     (`canonical_source` | `concept_page` | `evidence` | `sync_target`), `path`
     (normalized repo-rel referenced path), `exists` (filesystem fact).
   - `@dataclass(frozen=True) WikiClaims`: `claims: tuple[WikiClaim, ...]`,
     `skipped: tuple[str, ...]` (wiki files that could not be read), mirroring
     `ImportFacts`.
   - `extract_wiki_claims(repo, files, wiki_root=".codas/wiki") -> WikiClaims`:
     scope to `.md` files under `wiki_root`; track the current `##`/`###` section
     and `Evidence:`-style labels to assign `kind`; reuse the markdown adapter's
     path-normalization helpers (imported within the `codas-adapters` unit — no
     boundary crossing, no re-implementation → no `duplicate_implementation`).
     Deterministic, fence-aware, stable sort.
2. Inventory: `structure/inventory.py` emits a `wiki_claims` block
   (`{sources, claims, skipped}`) alongside `doc_claims`, mirroring its shape.
3. Seam: `facts/context.py` gains a memoized `wiki_claims()` accessor and
   re-exports `WikiClaim`/`WikiClaims` via `__all__` (so D2's policy names the
   fact type without importing the adapter).

## Acceptance criteria

- `extract_wiki_claims` on the repo wiki yields each `## Canonical Sources` path as
  `canonical_source`, each `## Concepts` link as `concept_page`, each `Evidence:`
  path as `evidence`, and each `## Required Synchronization` path as `sync_target`,
  with correct `concept` slug and `exists`.
- `codas inventory . --json` includes a `wiki_claims` block; byte-identical across
  two runs.
- `ScanContext.wiki_claims()` returns the same adapter-sorted tuple, memoized.
- `codas check .` → "No Codas findings" (facts-only, no policy yet); full suite
  green; `inventory.unowned` unchanged (empty).

## Non-goals

- The `stale_wiki_claim` **policy** (verification → findings) — that is D2.
- The `codas wiki` **command** / page generation — that is D3.
- Extracting a semantic `subject/predicate/object` triple or an `authority` label
  from prose (the §6 example's full shape) — deterministic, no-LLM (§17); D1 emits
  the structural claim + `exists`, D2 derives authority by cross-checking config /
  documents facts.
- Honoring `wiki.enabled` / `require_evidence` config flags — D2/D3 concern.
- Relocating fact dataclasses into a neutral `codas.facts.types` module — a
  standing P3 follow-up, out of scope here (re-export via `__all__` as today).
