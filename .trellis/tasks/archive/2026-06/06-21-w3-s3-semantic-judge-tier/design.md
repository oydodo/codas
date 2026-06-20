# Design — W3·S3 semantic judge tier (REVISED after codex DESIGN review)

GATE-ADJACENT. No code yet. codex DESIGN review round 1 = 5 BLOCKERs + 8 SHOULD-FIX, ALL
folded below. The review's load-bearing catch: a deterministic tier is NOT enough to escape
LLM-checks-LLM — the LLM also launders by SELECTING which true tuple to cite, so a structural
match must confirm STRUCTURE ONLY, never the concept/meaning the prose wraps around it.

## The crux: where the LLM is, and is NOT
§17 = no LLM in the correctness core. **Codas never runs the judge LLM.** Three parts, only the
middle is gate-adjacent:

1. **FEED (deterministic, no LLM).** Codas emits a grounding bundle the HOST agent generates
   prose over: the Block A `knowledge_tree/v1` spine + an instructions blob (open-world caveat,
   the trust-tier rules, "cite a node-id for every structural claim"). Pure projection.
2. **CALIBRATE (deterministic, no LLM — the gate-adjacent heart).** Codas reads the structural
   claims the corpus asserts and assigns each a tier by a DETERMINISTIC fact-match. The LLM
   authored the claim; the machine assigns the tier — AND the tier confirms only the structural
   tuple's existence, never the concept the prose attaches (see "Structure not meaning").
3. **JUDGE (the LLM, OUTSIDE Codas).** The host agent reasons over (tree + facts + tiers) to
   produce semantic-legality suggestions; suggestion-only, never committed. Codas supplies the
   substrate + the abstention contract; it does NOT perform the judgment.
   - v0: **host-agent contract ONLY. No `--emit-judge-context`** (codex Q3 — drops the ambiguity
     that Codas might invoke/validate with a model). If ever added it is `--emit-semantic-context`,
     makes NO model/network call, and is documented + tested as such.

## Structure not meaning (codex BLOCKER 2+3 — the core honesty fix)
A structural match confirms a TUPLE EXISTS; it does NOT confirm the concept/semantic label the
LLM wrapped around it. The LLM can cite a true-but-irrelevant node-id so the match passes while
the surrounding assertion is false (laundering by claim-SELECTION). Therefore:
- The top tier is named **STRUCTURE_CONFIRMED**, not "confirmed/trusted". Its meaning is exactly
  "the cited path/class/symbol (or edge) is present in the facts" — nothing about the concept.
- The `concept` field is ALWAYS unverified prose. The judge contract: never treat a
  STRUCTURE_CONFIRMED claim's concept/prose as verified; a structural match is a necessary, never
  a sufficient, condition for a semantic claim.
- Adversarial tests: (a) a valid-but-irrelevant anchor cited alongside false prose still only
  yields STRUCTURE_CONFIRMED on the tuple, with the concept flagged unverified; (b) same tuple +
  different "confidence" prose → identical tier.

## The structural-claim grammar (generalizes W1, OFFLINE only)
W1's `anchor_symbol: <concept> -> <path>:<name>` is the `defines` case. The OFFLINE corpus reader
(NOT the W1 check) parses:

    defines:  <concept> -> <path>::<class-or-empty>::<symbol>
    calls:    <path>::<cls>::<sym> -> <path>::<cls>::<sym>
    contains: <path>::<cls>::<sym>            # node present in the Block A tree
    # imports/owns deferred (see v0 scope)

Subjects use the Block A node-id `<path>::<class>::<symbol>`. **These node-ids are for OFFLINE
calibration ONLY.** The shipped W1 `anchor_symbol` grammar (`<path>:<name>`) and its matching
against `ctx.symbols().definitions` (top-level only) are UNCHANGED — so anchors that were W1
warnings do NOT silently become confirmed by call-endpoint-derived method nodes (codex SHOULD-FIX).

## CALIBRATE — the deterministic tier function + explicit world map
The world map is a FIRST-CLASS fact-layer registry, NOT an S3-local inline table (codex round-2
SHOULD-FIX): add `WORLD_BY_FAMILY` to `src/codas/facts/openworld.py` and have S3 tiering consume
it (never derive closed-world from an empty open-world gap tuple, openworld.py:74-84):

    WORLD_BY_FAMILY = {symbols: open, imports: open, calls: open, contains: open,
                       units: closed, declared: closed}

- DOGFOOD NOTE for the builder: `WORLD_BY_FAMILY` is a PUBLIC symbol added to openworld.py, so the
  shipped anchor-to-source `fact_coupling` (.codas/claims.yml — public symbol-add under
  openworld.py REQUIRES docs/codas-design.html) fires: the SAME commit must update design.html
  §9.4. (This is the gate working as intended.)

`tier(claim, facts)` (pure, §17-clean):

| tier | when | reported as |
| --- | --- | --- |
| **STRUCTURE_CONFIRMED** | the exact structural tuple is present in facts | tuple exists; CONCEPT still unverified |
| **UNCONFIRMED** | no match AND family ∈ OPEN | UNKNOWN — never "false", never a gate |
| **CONTRADICTED** | no match AND family ∈ CLOSED | **offline JSON metadata ONLY** — never a `Finding`, never in `run_check`, never affects exit status; the gating stays with existing `stale_*`/`generated_wiki_drift` |
| **SEMANTIC** | claim names no fact family (or an unknown family) | hypothesis only; the judge may SUGGEST, never verify or upgrade |

`contains`: present node = STRUCTURE_CONFIRMED; absent = **UNCONFIRMED, never CONTRADICTED** (the
Block A tree is a lower bound — codex SHOULD-FIX). Unknown family → SEMANTIC or a parse error,
never CONTRADICTED (fail safe).

## Artifacts + surfaces
- **FEED**: a NEW `codas wiki --emit-feed` flag, added to the existing wiki mutually-exclusive
  group (cli.py wiki_mode, a sibling of --emit-pack/--emit-tree — codex round-2 SHOULD-FIX: the
  parser must learn the flag). → JSON {knowledge_tree, instructions, open_world}. Out of hash.
- **CALIBRATE**: `codas wiki --calibrate <corpus>` → JSON [{claim, tier, evidence}]. OFFLINE; not a
  `codas check` warning.
- **Corpus + tags live under the already-ignored `.codas/cache/semantic/`** (codex round-2 BLOCKER
  1a/1b/1c + the location question — this resolution dissolves all three at once). The corpus is
  host-agent-generated, NON-deterministic, REGENERABLE → it is a LOCAL/EPHEMERAL artifact, NOT a
  versioned governance input. `.codas/cache/` is already gitignored (.gitignore:10), so
  `git ls-files --others --exclude-standard` (index.py:102) never discovers it → it enters NEITHER
  `discover_files`, NOR therefore the markdown/html/wiki claim adapters (they operate on the
  discovered set), NOR the inventory hash. No new SKIP_PREFIXES / html filter / exclude_under is
  needed. **Resolution of the non-git walk-fallback gap: require a git repository** (user
  decision) — already an implied operating assumption for the git-based facts (`changed_paths`,
  `fact_coupling`, spec-drift all read `git diff`). So gitignore alone fully excludes the corpus;
  the walk-fallback (`_IGNORE_PATHS`) needs NO change. `codas doctor` MAY assert a git repo for the
  corpus path; do NOT hard-break the non-git unit fixtures over it. Test: a corpus file under
  `.codas/cache/semantic/` leaves the inventory hash unchanged (git-discovery path); run-twice
  byte-identical.
  - Rejected `.codas/semantic/` (committed/versioned): would need 3 separate exclusions
    (markdown SKIP_PREFIXES, html hard-filter, inventory exclude_under) AND a gitignore decision,
    and would commit non-deterministic LLM output — wrong for a regenerable corpus.

## The check_code_anchor fold — KEPT ADDITIVE in v0 (codex BLOCKER 5 + SHOULD-FIX)
Do NOT fold the unified reader into `check_code_anchor`: that policy is ALWAYS-ON (app/check.py),
so routing general S3 corpus claims through it would make the offline corpus run during
`codas check` — turning calibration into a gate. Instead:
- Keep `ctx.code_anchor_claims()` and `check_code_anchor` EXACTLY as shipped (the W1 check).
- Add a SEPARATE offline corpus reader used ONLY by the `wiki --calibrate` path.
- The unified-reader fold (so `anchor_symbol` becomes the `defines` case and `check_code_anchor`
  delegates) happens LATER, only behind a golden parity test proving byte-identical findings on
  the dogfood repo. v0 = additive, two readers, zero change to the always-on warning.

## §11 / §17 / determinism
- §17: feed + tier() are LLM-free; the LLM is a generation/judge client off the determinism path;
  its output is a claim, never a verdict. Codas issues no model/network call anywhere in v0.
- §11: ALL S3 claim streams exposed through ScanContext; app/wiki + policies import no adapter
  (codex SHOULD-FIX — the new offline corpus reader gets a ScanContext accessor, like
  `code_anchor_claims()`).
- Determinism: feed + calibrate outputs byte-stable (sorted, node-id-keyed), out of the inventory
  hash, fixture-pinned (tests/test_knowledge_tree.py model).

## v0 scope (codex Q5 + round-2 SHOULD-FIX)
v0 claim grammar = `defines + calls + contains` ONLY — all OPEN-world, present-only. Defer `owns`.
`imports` only if the v0 FEED emits dependency material — else exclude dependency/import content
from the v0 feed instructions so no uncalibrated import claims are load-bearing.
- **No CLOSED-world claim KIND exists in v0** (codex round-2: the world map names `units`/`declared`
  but no v0 grammar parses a closed-world claim). So **CONTRADICTED is defined-but-DORMANT** in v0
  — the `tier()` function and `WORLD_BY_FAMILY` carry it for completeness, but it is unreachable
  until an `owns`/`declared` claim kind lands. `units`/`declared` stay in the world map as the
  forward-looking registry, not v0 grammar.

## Test plan
- tier() unit tests: one per outcome × family world; the world map is explicit (not gap-derived).
- LLM-cannot-launder: (a) same tuple + different confidence prose → same tier; (b) valid-but-
  irrelevant anchor + false prose → STRUCTURE_CONFIRMED on the tuple, concept flagged unverified.
- CONTRADICTED never instantiates a Finding / never appears in `run_check` output (test the
  exit-status + findings list are untouched by a CONTRADICTED corpus claim).
- `.codas/cache/semantic/` corpus: a corpus file there leaves the inventory hash unchanged
  (git-discovery path; git repo is required); run-twice byte-identical.
- `--emit-feed` flag: parser accepts it; mutually exclusive with the other wiki modes (SystemExit
  code 2 on conflict, like the --emit-tree tests).
- `check_code_anchor` parity: identical findings before/after S3 lands (golden on dogfood repo).
- feed/calibrate byte-identical; `codas check .` 0; full suite green; wiki --verify clean.

## codex DESIGN review status (round 1 — all folded)
5 BLOCKERs: (1) `.codas/wiki/**` is NOT out-of-hash → corpus moved to `.codas/semantic/` + tests;
(2) laundering by claim-selection → STRUCTURE_CONFIRMED + adversarial tests; (3) CONFIRMED
overclaims meaning → renamed, concept always unverified; (4) CONTRADICTED double-gate → offline
JSON only, never a Finding; (5) folding routes corpus into always-on check → keep additive, split
accessors. 8 SHOULD-FIX folded (contains=open-world, explicit world map, W1 grammar/matching
unchanged, §11 via ScanContext, drop --emit-judge-context, SEMANTIC wording, v0=defines+calls+
contains, imports gating). All 5 open questions answered + folded.

## codex DESIGN review status (round 2 — re-review of the revision; BUILD-READY)
BLOCKERs 2/3/4/6 PASS (laundering contained by STRUCTURE_CONFIRMED; CONTRADICTED offline-only;
check_code_anchor additive + accessors split; §11 via ScanContext). Round-2 corrections, all
folded: (a) `.codas/semantic/` would still need 3 separate exclusions (markdown SKIP_PREFIXES,
html hard-filter, inventory exclude_under) → **moved corpus to the already-ignored
`.codas/cache/semantic/`**, which dissolves all three (gitignored ⇒ never discovered ⇒ never in
any adapter or the hash). The non-git walk-fallback gap is closed by REQUIRING a git repo (user
decision; already implied by the git-based drift/coupling facts), so NO `_IGNORE_PATHS` change; (b) the
world map becomes a first-class **`WORLD_BY_FAMILY` in openworld.py** (S3 consumes it; note the
dogfood anchor-to-source coupling fires → same-commit design.html §9.4 update); (c) `--emit-feed`
specified as a new wiki_mode flag; (d) **CONTRADICTED is defined-but-DORMANT in v0** (no
closed-world claim kind yet). Design is BUILD-READY.
