# Design — Persistent semantic wiki (DRAFT for codex DESIGN review)

GATE-ADJACENT (a new always-on policy enters `codas check`). No code yet. Generalizes the W1
code-wiki pattern (`.codas/wiki/code/` + `code_anchor`) to a committed SEMANTIC wiki carrying the
full structural-claim grammar, so the host-agent's semantic narrative becomes a persistent,
drift-controlled knowledge base — the Codas thesis (verify claims against facts) applied to the
semantic layer.

## Why (the value)
Today the W3 semantic corpus is EPHEMERAL (`.codas/cache/semantic/`, gitignored, offline
`--calibrate` only). That validates a one-shot loop but leaves nothing browsable and nothing
drift-controlled. A COMMITTED semantic wiki, verified on every `codas check`, catches code→doc
drift: a symbol/method renamed or a call edge removed makes a committed structural claim stop
resolving → a warning. That is exactly what W1 does for `anchor_symbol`, generalized to
defines/calls/contains.

## Artifact: `.codas/wiki/semantic/**.md` (NEW committed subtree)
Each page = advisory PROSE (the semantic narrative) + a fenced ```atlas:claims block of
structural claims (the S3 grammar: `defines: <concept> -> <node-id>`, `calls: <node-id> ->
<node-id>`, `contains: <node-id>`). Mirrors `.codas/wiki/code/` exactly except for the richer
grammar.
- **Prose is advisory + OUT of the inventory hash**: add `.codas/wiki/semantic/` to the markdown
  adapter `SKIP_PREFIXES` and the wiki concept reader's skip (alongside `.codas/wiki/code/`), so
  the prose never becomes doc/wiki claims and never enters the byte-identical hash.
- The structural claims are **position-stripped policy-time facts** (like `code_anchor_claims`) —
  never serialized into the inventory.

## Reader (§11 via ScanContext)
Reuse the S3 adapter `extract_semantic_claims(repo, corpus_root)` (it rglobs `root/**/*.md`,
works for committed files too) with `root=".codas/wiki/semantic"`. Add a NEW accessor
`ScanContext.semantic_wiki_claims()` (distinct from `semantic_corpus_claims()` which reads the
EPHEMERAL cache for the offline loop). Two roots, one parser. Policies consume the accessor; no
adapter import.

## Verifier: a new policy `check_semantic_wiki` (WARNING, open-world)
On every `codas check`, tier each committed structural claim against facts; a claim that does NOT
resolve (would be UNCONFIRMED) → a **WARNING**, never an error — `symbols`/`calls`/`contains` are
OPEN-world, so a non-resolving claim is a lower bound (the code moved → update the page, OR a
dynamic form the extractor misses). Identical severity discipline to `code_anchor` (all-open
warning). Catches code→doc drift for the committed semantic wiki.
- Resolution: `defines`/`contains` → subject node present (top-level symbol OR call-endpoint —
  same node universe the knowledge tree uses); `calls` → the subject→object edge present in
  `ctx.calls()`. The CONCEPT is never verified (structure ≠ meaning, as in S3).

## LAYERING decision (codex — the key §11 question)
The deterministic resolution logic also lives in `app/calibrate.py::tier()`. A POLICY must NOT
import `app/` (policies are leaves consuming ScanContext; `check.py` in app/ imports policies —
importing app/calibrate from a policy inverts that). Two options:
- **(A) Self-contained policy** (like `code_anchor`): the policy resolves node-presence / call-edge
  directly from `ctx.symbols()`/`ctx.calls()` — small, no app import, some duplication of the
  node-universe + edge check.
- **(B) Extract the shared resolver** into `codas.facts` (e.g. a `facts/resolve.py` with the
  node-set + calls-index + a `resolves(claim, ...)` predicate) that BOTH `app/calibrate.tier()`
  and the policy import. Cleaner, no duplication, but a refactor touching shipped S3 code.
Leaning (A) for v0 (lower risk, mirrors code_anchor); record (B) as the dedup follow-up. Codex: rule.

## Lifecycle (no new "write" command — Codas authors no prose)
Agent authors in `.codas/cache/semantic/` (ephemeral) → `--calibrate` → reviews tiers → PROMOTES
good pages to `.codas/wiki/semantic/` (commits them) → `codas check` verifies them ongoing. Codas
provides only the VERIFY; the agent (or a host harness) does the promote/commit.

## code_anchor relationship (keep ADDITIVE in v0)
`code_anchor` (`.codas/wiki/code/`, `anchor_symbol` only) stays unchanged. The unified fold
(`anchor_symbol` becomes the `defines` case so `code_anchor` delegates) is deferred behind a
golden parity test — same call the S3 design made. v0 = two coexisting verifiers, slight overlap.

## Determinism / §11 / §17 / gate-semantics
- Prose out-of-hash (SKIP_PREFIXES); claims position-stripped policy-time facts (not in inventory).
  byte-identical preserved.
- §17: the verifier is a pure fact-match (no LLM). §11: claims via the ScanContext accessor; no
  adapter import in the policy.
- GATE-SEMANTICS: a new `check_*` policy → declared in `policies.yml` + wired into `run_check` in
  `app/check.py`. The shipped `check_*`→`check.py` fact_coupling WILL fire → both must land in the
  SAME commit. Update the orchestration test (`test_codas_check.py`) to patch+spy the new policy.

## Test plan
- adapter: parse a committed semantic page's claims (reuse S3 adapter tests, new root).
- policy: a resolving claim → no finding; a non-resolving claim (bad node-id / removed edge) →
  exactly one WARNING; an all-open severity test (never an error); empty/no-wiki → no findings.
- the concept is never verified (a true tuple + false concept → no finding, like S3).
- check 0 on the dogfood repo (with a real seed page whose claims all resolve); byte-identical;
  the prose page does NOT change the inventory hash (edit prose → hash unchanged).

## codex DESIGN review — RESOLVED (round 1; 3 BLOCKERs + SHOULD-FIX folded). BUILD-READY.

**Q1 layering → OPTION A (self-contained policy). Do NOT create facts/resolve.py; do NOT call
build_atlas_tree from a policy** (it runs a 2nd full inventory scan at check time — a perf/correctness
regression, calibrate.py:98). The policy resolves directly from `ctx.symbols()`/`ctx.calls()`.

**Q2 seed → SHIP EMPTY.** No committed `.codas/wiki/semantic/` page (a seed locks claims that must
resolve forever while the codebase actively refactors). Dogfood/validate via TEST FIXTURES only.

**Q3 ordering → SEPARATE policy, do NOT fold code_anchor now.** Different data sources/parsers
(`.codas/wiki/code/` + `anchor_symbol` vs `.codas/wiki/semantic/` + defines/calls/contains) → NOT a
`duplicate_implementation` (the policy bodies check different invariants over different data). Tag the
planned v1 unification in a `policies.yml` comment; fold later behind the golden parity test.

**Q4 drift → materially richer than W1 → the NODE-UNIVERSE FIX (SHOULD-FIX).** call-endpoint-derived
method nodes appear in the atlas tree but NOT in `ctx.symbols().definitions`, so a naive symbols-only
check spuriously WARNs on a valid `calls`/method claim. Build the resolution universe from BOTH:
- callable nodes = `{f"{d.module}::::{d.name}"}` (symbols) ∪ `{caller/callee f"{path}::{cls}::{sym}"}`
  over `ctx.calls().edges` (the call-endpoint nodes the tree adds);
- module nodes = `{d.module}` (the .py paths);
- calls edges = `{(caller-id, callee-id)}` over `ctx.calls().edges`.
- PACKAGE nodes (bare dir paths) = a DOCUMENTED v0 gap (a `contains: <dir>` won't resolve → warns;
  authors use file/symbol node-ids in committed pages). Record in the policy docstring.

### BLOCKERs (folded — all land in ONE atomic commit)
1. **`extract_wiki_claims` (wiki.py:59-65) also scans `.codas/wiki/**` and must exclude
   `.codas/wiki/semantic/`** (alongside the existing `code_prefix`), else committed prose enters
   `inventory["wiki_claims"]` → churns the hash. So the out-of-hash exclusion is TWO places:
   (a) markdown.py `SKIP_PREFIXES += ".codas/wiki/semantic/"` (kills doc_claims + stale_wiki_claim
   on the prose), (b) a `semantic_prefix` skip in `extract_wiki_claims`. BOTH required.
2. **`extract_semantic_claims` rglobs from disk (correct for the gitignored cache) — for COMMITTED
   pages use the TRACKED file list.** Add an optional `files: tuple[str,...] | None = None` param:
   `None` → rglob (cache, `semantic_corpus_claims`); given → filter `files` under the root
   (committed, `semantic_wiki_claims`). Mirrors `extract_code_anchor_claims(repo, files, root)`.
3. **ATOMIC commit** — the new policy + `check.py` wiring (`run_check` extend) + `policies.yml` entry
   (severity `warning`) + `ScanContext.semantic_wiki_claims()` accessor + the 2 hash exclusions + the
   `files` param + tests + orchestration-test patch ALL in one commit, or the `check_*`→check.py
   fact_coupling AND `check_policy_registry` AND the hash invariant trip mid-flight.

### SHOULD-FIX (folded)
- Severity = `warning`, ALL-OPEN, never `error` for any of defines/calls/contains (open-world); the
  message carries the `code_anchor` open-world caveat ("code moved → update the page, OR a
  dynamic/conditional form the extractor misses"). No branch may raise to error on absence.
- The new accessor docstring states it reads `.codas/wiki/semantic/` (committed/tracked) vs
  `semantic_corpus_claims()` `.codas/cache/semantic/` (gitignored/offline); add a one-line pointer in
  the latter. `_IGNORE_PATHS` non-git: fine once the 2 exclusions hold (note in the checklist).

## Build checklist (atomic)
adapters/semantic.py (+`files` param) · adapters/markdown.py (SKIP_PREFIXES) · adapters/wiki.py
(`extract_wiki_claims` semantic skip) · facts/context.py (`semantic_wiki_claims()` accessor) ·
policies/semantic_wiki.py (NEW, warning all-open, resolution universe = symbols ∪ call-endpoints) ·
app/check.py (wire) · .codas/policies.yml (entry + unification comment) · tests/test_semantic_wiki.py
(NEW) · tests/test_codas_check.py (patch+spy). NO seed page. → check 0 + tests + byte-identical (incl.
"edit a semantic page → inventory hash unchanged") + verify.
