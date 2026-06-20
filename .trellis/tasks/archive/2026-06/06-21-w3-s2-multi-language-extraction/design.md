# Design — W3·S2 multi-language extraction (DECISION: DEFER; for codex DESIGN review)

GATE-ADJACENT (adds an adapter, likely a dependency). This design analyzes the approach and
reaches a DECISION before any build: **DEFER** — multi-language extraction cannot deliver its
value without spending the moat the project itself names as its differentiation. Recorded with
the optional-extra design + the conditions to revisit, per the goal's "if it can't be done
without breaking the moat, stop and leave S2 in planning."

## What S2 would add
Extend Codas's facts beyond Python so the knowledge tree / call graph / policies work on
multi-language repos: per-language SYMBOLS (functions/classes) + cross-file IMPORT/CALL edges,
all normalized to the existing resolution-tagged `calls`/`imports`/`symbols` fact shape (the
fact vocabulary is already language-neutral, so policies stay unchanged).

## The honest split (from the perception-model decision record + the 3-way critic)
- **Symbols** — BORROW tree-sitter / ctags per language (cheap, portable).
- **Cross-file import/call RESOLVER** — must BUILD per language. Resolved cross-file edges are
  NOT portable; CodeWiki's resolver is non-deterministic (arbitrary cycle-break, eval()-parse)
  so it is a blueprint, not a dependency. This is the HIGH-VALUE part and it is net-new
  engineering per language, not a borrow.

## The moat collision (the decisive factor)
Codas's moat is the **lightweight, pyyaml-only, pip-installable, serverless, no-toolchain CLI**
that sits UNDER AGENTS.md — the property that beats SonarQube and keeps it agent-native. Every
viable multi-language fact source breaches it:
- **tree-sitter** → a C-extension dependency. Breaks pyyaml-only / pure-pip / no-build.
- **ctags / SCIP / stack-graphs** → an external binary or per-language toolchain + buildable
  project. Breaks serverless / no-toolchain.
- **pure-Python regex/heuristic** (zero-dep) → low-fidelity symbols AND essentially NO sound
  cross-file call graph (the high-value part is undecidable by regex). Low value, and risks the
  byte-identical/sound-lower-bound discipline (the pyan lesson: never ship a non-deterministic
  or guess-based extractor).
- **LSP shell-out (codex round-1 gap — named + REJECTED here):** detect a language server
  (gopls / typescript-language-server / rust-analyzer) on PATH and query document-symbols + call
  hierarchy over stdio JSON-RPC — zero pip dependency, absent from the default install. Tempting,
  but **DISQUALIFIED on determinism**: LSP call-hierarchy output is NOT byte-identical across
  server versions (edge ordering varies), the protocol guarantees no cross-invocation
  determinism, and it needs a running stateful server per file. Named so a future implementer is
  warned, not left to discover it violates byte-identical.
- **Native-toolchain shell-out (the ONE marginal exception, Go):** `go list -json ./...` (Go
  stdlib) gives deterministic cross-file resolution IF the Go version is pinned, and a Go repo is
  by definition analyzed in a Go environment (zero NEW pip dep, `--if-present` semantics). This
  is the closest-to-free path — but it still requires the Go toolchain present and a pinned-version
  determinism contract, so it stays a CONDITIONAL fast-track (see revisit triggers), not v1. No
  other language has a deterministic, pip-installable, toolchain-free borrowable resolver
  (TypeScript = needs Node/tsc; Java = needs javac/build; Rust = rust-analyzer non-determinism).

So REAL multi-language value requires breaking the moat — at best as an OPTIONAL extra
(`pip install codas[treesitter-LANG]`, off the default install, gated, off the determinism
path). And even the optional extra carries the must-BUILD resolver (large, per-language) plus
unbounded multi-language maintenance scope.

## Decision: DEFER (do not build now)
1. **Moat cost** — the differentiation is the lightweight zero-dep CLI; multi-lang spends exactly
   that. The Python-first product (Block A tree + W3 calibrator + S1 views) already delivers the
   thesis on the language Codas dogfoods.
2. **Demand unproven** — the project's own #1 risk is "AGENTS.md + an LLM reviewer is good
   enough." Multi-lang is the most expensive bet against the thinnest-validated demand.
3. **Cost/value** — the borrowable half (symbols) is the cheap, low-value half; the valuable half
   (the resolver) is must-build per language. Bad ratio until demand exists.

## A PERMISSION STRUCTURE, not a roadmap (codex round-1: do not create build pressure)
The following is what an eventual build COULD look like — recorded so a future implementer
inherits the constraints, NOT a roadmap item. Multi-language is explicitly NOT on the roadmap;
it ships only when a revisit trigger fires AND the Python-first product (W3 calibrator) has
external adoption. Shipping it before the Python product is validated compounds the #1 adoption
risk rather than reducing it.
- An OPTIONAL extra (`codas[multilang]`) installing tree-sitter for named languages, behind a
  per-§11 adapter, OFF the default `pip install codas` (which stays pyyaml-only). (Note:
  tree-sitter ships pre-compiled wheels for tier-1 platforms — pip-installable without a C
  compiler there — but per-language grammar wheels + non-wheel platforms still fragment the
  surface, and wheels give symbols only, not the resolver.)
- Per-language frontends → ONE normalized resolver emitting the existing `calls`/`imports`
  fact shape; deterministic (Tarjan-SCC + canonical-order cycle break, never arbitrary);
  output a sound OPEN-WORLD lower bound; never enabled on the determinism-critical default path.
- A possible separate ADVISORY tier (codex round-1, low priority): a regex symbols-only stream
  for agent navigation ("top-level exports of this module"), but ONLY if the fact schema marks
  it `fidelity: heuristic` — explicitly NOT a sound lower bound, fenced from the sound facts so
  it never pollutes the open-world discipline. Not v1.

## Revisit triggers (sharpened, codex round-1)
Revisit only when one fires:
1. A concrete multi-language dogfood target exists.
2. Demonstrated user demand for a non-Python repo.
3. A language whose cross-file call graph is resolvable AND **deterministic across invocations
   (byte-identical for the same source) AND borrowable without >2 weeks per-language resolver
   engineering** (the floor — bars a bad-faith reading where "regex symbols" counts).
4. **Go fast-track:** a target Go repo analyzed in an environment with Go present → the
   `go list -json` shell-out (`--if-present`, pinned-version determinism, zero new pip dep) is
   low-cost and could ship ahead of the general path.
5. **tree-sitter wheel coverage** ≥95% of tier-1 CI/CD environments (audited) → the optional
   extra becomes low-friction.

## Acceptance (for THIS deferral task) — MET
- [x] codex DESIGN review (2026-06-21) CONCURS: **"DEFER is correct. There is no missed
      moat-preserving path."** No deterministic, pip-installable, toolchain-free borrowable
      cross-file resolver exists for any language (Go's `go list` is closest but needs the Go
      toolchain). 6 refinements folded above: LSP path named+rejected (determinism), Go
      fast-track + tree-sitter-wheel triggers added, "permission structure not roadmap" made
      explicit, trigger-3 floor sharpened, advisory heuristic-symbols tier noted. Polyglot risk
      = ACCEPTABLE-V1 (the codebase dogfoods on Python; the policy layer is already
      language-neutral; partial governance > none).
- [x] CONCUR path taken: **S2 stays in PLANNING, deferred. No build.** The parent W3 task is NOT
      archived (2/3 children shipped; S2 deferred by design per the goal's moat instruction).
