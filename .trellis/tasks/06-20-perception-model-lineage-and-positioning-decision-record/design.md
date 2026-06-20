# Decision Record — Codas perception model, TMS lineage, positioning (2026-06-20)

Origin: a user-driven brainstorm + one codex adversarial critique + three parallel
research sweeps (governance philosophies; competitive landscape; multi-language fact
sources). This is the long-form rationale; the governed surface is the fenced Concept Map
in CONTEXT.md.

---

## 1. The perception model (post-critique)

### 1.1 The original frame
Codas "perceives" a repo at three grains:
- L1 = FILE, sensed by md5/diff (`changed_paths`), perceives CHANGE. Deterministic,
  language-agnostic, cheap.
- L2 = SYMBOL/CALL-EDGE, sensed by an ADAPTER (stdlib-ast call-graph), perceives
  STRUCTURE. Deterministic, per-language (only Python today), costly.
- L3 = CONCEPT/CAPABILITY/INTENT, sensed by an LLM (the host agent, NOT Codas), perceives
  MEANING. Non-deterministic, needs judgment.

Unified with the existing fact/claim concepts: FACT = a deterministic sensor's observation
(L1/L2 have sensors; L3 has none — an LLM produces a CLAIM, not a fact). CLAIM = an
assertion at any grain. Governance = verify a claim by reducing it down to facts.

### 1.2 codex critique — verdict SOUND-BUT-NEEDS-PATCHES
Four structural defects (+ a live dogfood bug, §5):
- (A) "reduce down" assumes CONTAINMENT (concept ⊂ symbol ⊂ file) that does not hold —
  concepts are many-to-many over files/symbols.
- (B) propagation was one-directional (change "upwells" L1→L2→L3); a top-originating edit
  (reword program.yml intent, rename a wiki concept) changes no L1/L2 fact yet must trigger
  governance.
- (C) "deterministic" was conflated with "correct": a static call-graph fact is
  byte-identical AND approximate; treating absence-of-edge as proof-of-no-call is unsound.
- (D) the L2/L3 "determinism cliff" was stated as a law; it is a contingent tooling fact +
  a policy choice (§17), not metaphysics.

### 1.3 The patched model (four transforms)
1. **Layers → FACT FAMILIES (open set).** Not a vertical stack but a set of sensor-scoped
   families, each with a SOUNDNESS qualifier: static-content (hash, exact) · structure/call
   (ast, approximate) · diff (changed_paths) · generated (governance.md) · [external,
   runtime — future] · semantic-residue (LLM, claim-only). A policy declares which families
   it consumes. (Closes A and the "missing layers" hole.)
2. **CLAIM → structured object.** `{subject, assertion, grain, verifier-class ∈
   {existence, relation, structural, semantic-residue}, evidence[], soundness,
   lifecycle{provenance-hash, expiry}}`. The verifier-class decides reach: existence/
   relation/structural fully verify; semantic-residue only has its evidence anchors checked.
3. **"reduce down" → PROJECTION over named families** (many-to-many, not a containment
   tree). (Closes A.)
4. **Propagation → BIDIRECTIONAL.** A claim carries a content hash; the worklist is seeded
   by `fact-delta ∪ claim-delta` — a claim-text change with no supporting fact-delta is
   still a governance event. (Closes B.)
Plus: the determinism boundary is restated as "no NON-DETERMINISTIC verifier in the core"
(a policy choice, §17), not "meaning can never be a fact" (a false law). (Closes D.)

### 1.4 Panorama (the version that lands in CONTEXT.md)
```
                    REPO  (raw substrate: files, history)
                      | perceived by v        (FACT flows UP)
   [ FACT FAMILIES — open set; each = sensor + SOUNDNESS qualifier ]   <- patch: layers->families
     static-content | structure/call |  diff   | generated |[runtime]
      hash <EXACT>   |  ast <APPROX>  |changed_ |governance |[external]
      file           |  symbol.edge   | paths   |  page     | (future)
            | emit FACTS (deterministic -> inventory)        | semantics: NO native fact
  ----------+------ §17 = "no NON-DETERMINISTIC verifier in core" -----+----- <- patch: cliff=choice
            |        (a CHOICE, not a law)                             ^
            v                                                          |
   [ VERIFY = project a CLAIM's evidence onto the fact families it     |  optional L3 GENERATOR
     names — MANY-TO-MANY, not a tree ]  <----------------------------+--  host agent / CodeWiki
     CLAIM = {subject, assertion, grain, verifier-class,                   / none — output = CLAIM
              evidence[], soundness, lifecycle{hash,expiry}}  <- patch: the CLAIM SCHEMA
            |  outcome by verifier-class
            v
     [ GOVERNANCE FACT (verified) | FINDING (claim ⊥ fact) | RESIDUE (semantic, evidence-only,
                                                              stored w/ hash+expiry, re-checked) ]
            |  verdict per claim = 2x2 (changed? x consistent?)
            v
     [ PROPAGATION — BIDIRECTIONAL worklist: seed = fact-delta ∪ CLAIM-delta -> re-verify -> fixpoint ]
            v
        RECEIPTS  (provenance-pinned audit trail)
```

---

## 2. Intellectual lineage — Truth-Maintenance Systems

DECISION: Codas consciously claims the **Truth-Maintenance System** lineage (Doyle's JTMS /
de Kleer's ATMS), read as a deterministic SINGLE-CONTEXT belief network. Codas already IS a
JTMS: premises (facts) justify nodes (claims); belief status is a PURE FUNCTION of the
justification network (verify = IN/OUT label computation, never a free-standing verdict);
retraction is dependency-directed (a node goes OUT the instant its last justification fails,
touching only the minimal reachable set = exactly the fact-delta∪claim-delta worklist to a
fixpoint). Crucially, a TMS REPRESENTS defeasibility without RESOLVING it with a
non-deterministic judge — the determinism boundary is native to the formalism.

The other three traditions are upgrades on the TMS spine, not rival ancestors:
- **provenance semirings** → the algebra for how the SOUNDNESS qualifier composes (the MEET
  rule bare JTMS lacks).
- **self-adjusting computation** (Adapton / Salsa / Bazel / differential dataflow) → the
  incremental relabel with early-cutoff/resurrection, proving byte-identical and
  minimal-recompute are compatible; supplies the v3 engine's termination argument (monotone
  label lattice over a finite fact/claim set).
- **Toulmin / Pollock / AGM** → the vocabulary that makes the claim schema and residue
  lifecycle rigorous (warrant, undercut-vs-rebut, belief-base-vs-closure).

REJECTED (do not survive byte-identical + no-LLM-core):
- AGM SUCCESS postulate read as "trust the author" — a claim may ENTER the base to be
  verified, but presence never overrides facts; the verifier assigns the label.
- Full-generality ATMS problem-solver (exponential multi-context labels + open-ended
  non-deterministic solver) — keep only the deterministic label-compute + dependency-
  retraction skeleton, bounded to a single context per check run.
- Fuzzy / Bayesian / probabilistic TMS and NLI/embedding "entailment" verifiers — any
  numeric confidence a verifier WEIGHS is a non-deterministic judge in the core. Codas's
  only uncertainty is the DISCRETE soundness qualifier + the residue store.
- Learn-but-verify / Prover-Verifier INTERACTIVE loop (verifier re-invokes the LLM
  mid-verdict) — the LLM stays strictly generate-only, producing a frozen, provenance-pinned
  candidate; the core only ACCEPTs/REJECTs it.
- Dynamic / baseline-shifting fitness functions, and lazy/unmaterialized derived predicates
  (Glean on-demand, Souffle lazy provenance) — non-deterministic or query-order-dependent;
  advisory-only, or MATERIALIZE + content-hash-pin before the gate. AGM Recovery is
  unneeded ceremony for a recompute-the-closure model.
- ML/NLP erosion symptom-classifiers (e.g. KNighter) — allowed only as candidate-generation
  / false-positive triage feeding a deterministic checker, NEVER the gate verdict.

---

## 3. Sequenced borrow-backlog (both research rounds merged)

Ranked by leverage. P0 items are the convergence of philosophy + competitive findings.

- **B1 — findings RATCHET / baseline (P0, build first).** Snapshot current findings to a
  content-hashed baseline; gate only on NET-NEW drift; grandfather existing debt. TRIPLE-
  justified: (a) the #1 adoption unblocker (real repos are dirty; an all-or-nothing gate
  gets turned off — dependency-cruiser `--ignore-known` is the canonical mechanism);
  (b) the first slice of the v3 propagation engine (Adapton early-cutoff / TMS nogood
  baseline); (c) builds directly on the existing v2-A fact-delta substrate. Pure
  deterministic, no LLM.
- **B2 — SOUNDNESS qualifier on facts (high).** Every fact family carries a discrete
  soundness tag (exact | approximate-incomplete | derived | scoped); a claim verified
  against several families inherits the MEET (weakest); name per-sensor exactly what is
  under-approximated (reflection / dynamic-dispatch for the call graph). Makes "we reject
  pyan for nondeterminism" honest — determinism and soundness are orthogonal axes. LIVE GAP:
  `adapters/callgraph.py` + `facts/snapshot.py` emit facts with NO soundness field today.
- **B3 — Pollock undercut-vs-rebut in the residue lifecycle (high).** Two retraction paths:
  REBUT (a fact contradicts the claim) → contradicted/violation; UNDERCUT (a fact family's
  soundness DEGRADES) → drop to "unverifiable", NOT "violation". Never conflate "code is
  wrong" with "I can no longer see well enough". Protects the no-false-positive contract.
- **B4 — Toulmin claim schema (high).** Give the claim object the six named slots (DATA=
  evidence, WARRANT=verifier-class, BACKING=fact soundness/provenance, QUALIFIER=soundness
  strength, REBUTTAL=expiry+defeaters). Self-documents what the core can mechanically check
  vs what it defers to residue. The structural prerequisite for the planned-but-unbuilt
  `duplicate_concept` / `missing_canonical_owner` concept-level policies.
- **B5 — Adapton/JTMS incremental propagation worklist (high; the v3 engine).** fact-delta
  dirties only claims whose evidence names that family (reverse index); re-verify to a
  fixpoint; same verdict+provenance-hash → STOP (resurrection); stable KEYS = symbol
  identity not line number (FactDelta already does this). The ADR for the v3 engine.
- **B6 — AGENTS.md emit + consume (P0, distribution).** Read an existing AGENTS.md as
  declared intent to gate against; generate a provenance-stamped, verified AGENTS.md section
  from the inventory. Rides the de-facto standard (60+ tools) → instant distribution, and
  fixes the staleness AGENTS.md can't self-detect. Codas becomes the determinism layer UNDER
  the standard, not a 9th format.
- **B7 — blast-radius audit reframe (P1, cheap, marketable).** Codas already SHIPS the
  primitives (`codas impact` = reverse reachability; `duplicate_implementation`). Reframe as
  a change-triggered FINDING: "you touched X — here are N callers + a duplicate sibling you
  did NOT touch", deterministic + receipt = the differentiator vs the highest-recall LLM
  reviewer (zero hallucinated findings).
- **B8 — reflexion 3-valued verdict + must_depend_on (medium).** Split the undifferentiated
  "finding" into CONVERGENCE/DIVERGENCE/ABSENCE (verified / forbidden-thing-present /
  required-thing-missing); add a positive `must_depend_on` structural claim (structure.yml
  has may/must_not but cannot REQUIRE a seam, e.g. "policies MUST reach facts via
  ScanContext").
- **B9 — on_fail action policy + committed-residue policy + PageRank-ranked preflight
  (P2/P3).** Per-policy declarative block/warn/fix/waive (Guardrails AI) atop the existing
  waivers; a deterministic debug-print/secret/leftover-TODO finding class (Graphite) as a
  cheap on-ramp; centrality-ranked, token-budgeted preflight (aider repo-map) so the context
  pack is a "read these first" list, not a dump.

---

## 4. Multi-language fact source — SonarQube-as-adapter REJECTED (eval wf `wbm2xgm7z`)

DECISION: do NOT use SonarQube Community as a multi-language structural-fact adapter. It
fails 3 of the 5 hard invariants, each fundamentally:
- **§11-normalizable — FAILS (fatal alone).** Its queryable surface is ISSUES + METRICS + a
  component tree; it has NO first-class symbol DEFINITIONS / IMPORT edges / resolved CALL
  edges. The analyzers DO build a semantic model internally but DISCARD it before any
  queryable artifact. Recovering Codas's facts would mean re-parsing — i.e. throwing Sonar
  away and reimplementing the adapter.
- **Lightweight — FAILS.** sonar-scanner-cli is a JVM program, not pip-installable, and NOT
  serverless (it must reach a SonarQube server to fetch the engine + analyzers and to send
  the report; `sonar.dryRun` was removed). Standalone = standing up a JVM web app +
  Elasticsearch + PostgreSQL — exactly the server/DB/daemon the invariant forbids; destroys
  the lightweight-CLI identity that IS the moat (§5).
- **Byte-identical — FAILS, worse than pyan.** The report embeds wall-clock `analysis_date`,
  `analysis_uuid`, `scm_revision_id`, plugin/ActiveRule epoch fields, warning timestamps as
  VALUES; the server applies New-Code-Period / marked-as-unchanged incremental diffing, so
  identical source bytes produce different output depending on server state and prior runs.
- License (since ~Dec 2024 the language ANALYZERS — the only parts that could produce
  structural data — moved to the proprietary source-available SSALv1, anti-competition
  clauses) is additionally fraught. (NO-LLM passes, but moot.)

**The pyan parallel (the sharp lesson):** pyan was "RIGHT facts, WRONG order" —
RECOVERABLE by a boundary total-order sort (exactly what python.py/callgraph.py do). Sonar
is "DIFFERENT facts every run, by architecture" — UNRECOVERABLE, because the variance is
CONTENT (embedded timestamps + server-state-dependent diffing), not ordering. Codas's proven
mitigation (canonicalize-on-ingest) is powerless against content variance. So the discipline
that rejected pyan rejects Sonar even harder, and additionally on lightweight + §11.

### Recommended multi-language path — a LAYERED, owned-resolution stack (mirror python.py)
Preserve the existing discipline (parse seam → deterministic projection with an explicit
total-order sort; "determinism is the property", pyan named as the anti-pattern):
- **Layer 1 — SYMBOLS (BORROW the parser, ship FIRST).** tree-sitter (py-tree-sitter, MIT,
  prebuilt wheels, in-process, no server) with per-language `.scm` query captures → project
  into the EXISTING `SymbolFact(module,name,kind,line)` shape. PIN the grammar version per
  language (treat a grammar bump like a CPython-version pin) + apply the existing emit-time
  sort. `universal-ctags` (shell-out, JSON-Lines, gives enclosing scope/scopeKind, GPL only
  at the harmless shell-out boundary) is a viable alternative/cross-check. Byte-identical
  symbols multi-language with a pinned version + boundary sort. The cheap, safe, immediate
  win. (Adds a C-extension dep — strictly beyond pyyaml-only, but compatible with a
  pre-commit/CI CLI: no toolchain, no buildable project required.)
- **Layer 2 — IMPORTS + CALLS (BUILD per language, the load-bearing non-borrowable part).**
  The only native cross-file resolvers — stack-graphs (ships a SQLite DB → breaks no-db;
  archived/EOL Sept 2025) and the SCIP indexers (per-language Node/JVM/clang/cargo
  toolchains, per-indexer-unverified determinism) — are NOT adoptable as a default runtime
  dep. So BUILD a Codas-authored per-language resolver on the Layer-1 parse tree,
  generalizing python.py/callgraph.py (resolve imports to first-party paths; reduce call
  sites to caller→callee edges against first-party defs; emit existing ImportFact/CallFact +
  resolution tag, sorted on emit). Use github/stack-graphs (Py/JS/TS/Java rules) and SCIP's
  `enclosing_symbol/enclosing_range` reduction as DESIGN BLUEPRINTS, not deps. Start with 1–2
  high-value languages (JS/TS, Go); first-party-only keeps scope bounded as Python already
  does.
- **Layer 2 escape hatch (OPT-IN HEAVY, BORROW with canonicalization).** Allow an opt-in
  SCIP adapter that shells out to a PINNED per-language indexer, then CANONICALIZES the
  order-independent `.scip` protobuf on ingest (sort documents by path, occurrences by
  (range,symbol), symbols by id) to recover byte-identity. Gated behind: (a) two-process
  byte-identity diff per indexer per pinned version (test it like pyan was tested), and (b)
  an explicit opt-in flag — NEVER the default pre-commit path (needs a toolchain + buildable
  project). SCIP buys cross-file RESOLVED imports for free (its one real advantage); call
  edges are still DERIVED from occurrence+enclosing_range (heuristic), not read natively.

NET: borrow tree-sitter/ctags for symbols now; BUILD per-language import/call resolvers
mirroring python.py/callgraph.py (stack-graphs/SCIP as blueprints); optionally borrow pinned
SCIP indexers as an opt-in heavy adapter behind a verified-byte-identity gate. REJECT
SonarQube, CodeQL (license forbids generic CI on non-GitHub-OSS repos), Glean (Haskell/
RocksDB server-class), Joern (JVM/Scala multi-GB CPG), Semgrep-as-fact, stack-graphs-as-
runtime, ast-grep-as-fact.

---

## 5. Competitive positioning (honest)

- **White space is REAL but NARROW.** No surveyed tool does the WHOLE: deterministic,
  no-LLM, content-hashed verification of code vs DECLARED STRUCTURAL INTENT, on BOTH sides
  of the edit (preflight + gate + receipts), agent-agnostically. Each HALF is occupied
  (read-side maps stop at the map; conformance gates are architect-facing/reactive/no-
  receipts; spec-driven frameworks keep an LLM in the judgment; agent-rules are unverified
  prose).
- **Nearest = SonarQube "Architecture as Code"** (schema ~1:1 with structure.yml) — but it
  is in the PAID tiers (Developer+), heavyweight, architect-facing. The free Community
  edition is the quality engine (LGPL), not the structural-governance feature. So a free,
  light, agent-native, deterministic structural-governance CLI is still an open lane.
- **Thin moat, honestly.** preflight + receipts are bolt-on-able in a quarter; Codas's real
  weakness is DISTRIBUTION and unproven demand ("AGENTS.md + an LLM reviewer is good
  enough"). DEFENSIBILITY = become the determinism layer UNDER AGENTS.md before an incumbent
  adds a preflight pass. → makes B6 (AGENTS.md) strategically P0 alongside B1.

---

## 6. Live dogfood teeth surfaced (fix opportunities)

- **structure.yml `codas-adapters` purpose is STALE**: says "Markdown and Trellis adapters"
  but the dir has 8 adapters (callgraph/git/html/markdown/python/python_parse/trellis/wiki).
  `codas check .` = 0, blind (inventory drops `purpose`). The first real instance of the
  "semantic field inside a machine file goes stale" class. Fix path: anchor purpose to facts
  (must name actual adapters → checkable) OR mark it semantic-residue with a lifecycle.
- **Missing soundness field** on call/import/symbol facts (B2) — the model claims
  approximate but the data doesn't say so.

---

## 7. Sequenced next actions

1. **B1 findings ratchet/baseline** (build first — adoption × engine × theory convergence,
   on the v2-A substrate).
2. **B2 soundness qualifier** (honest foundation; pairs with B3).
3. **B6 AGENTS.md emit/consume** (distribution) and **B7 blast-radius reframe** (cheap
   differentiator) next.
4. The v3 propagation engine ADR is B5 (this record is its conceptual seed).
Each becomes its own Trellis task with the usual rhythm (design → codex review → implement →
dogfood-clean → archive).
