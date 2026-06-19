# PRD — P5 wiki architecture decision (verified, agent-driven LLM-wiki)

Decision record for how Codas does "wiki" (P5 D3 onward). Output of a design
brainstorm: a 3-lens design workflow + two adversarial codex rounds + an extended
grill session. The implementation slices (D3a–e) reference this; full reasoning is
in `design.md`.

## Spirit (what we decided)

Codas does **not** become a DeepWiki-style prose generator and does **not** embed an
LLM (`import anthropic` is vetoed). Instead:

- **Codas = the verified knowledge layer**: it emits a deterministic *grounding pack*
  (projected from inventory facts), renders deterministic *generated sections*
  (dependency graph / symbol index / structure units / roadmap), and *verifies* any
  generated wiki output back against repo facts. Zero LLM, byte-identical.
- **The host agent (Claude Code / Codex / Cursor) — already an LLM — is the writer.**
  It runs `codas wiki --emit-pack` / `--brief` to get grounding, writes the rich
  prose+diagram pages (itself, or by driving an OSS LLM-wiki tool), then `codas
  check` verifies. Codas is agnostic to which generator; an external orchestrator
  (agent / CI) wires Codas's grounding into the tool. No MCP.
- Net = **"verified LLM-wiki": DeepWiki richness without DeepWiki's unverified
  drift.** The verifier is the authority; the LLM is a downstream consumer of
  verified substrate and an upstream producer of claims that must pass that verifier.

## Four locked invariants

1. **LLM only in the generate path** (the host agent); `check`/`inventory`/policies
   never invoke an LLM.
2. **Generated content enters governance strictly as claims-to-verify, never as
   facts or policy verdicts.** The deterministic verifier is the authority.
3. **Codas core stays import-LLM-free and byte-identical**; any LLM dependency is
   lazy + optional and never on the inventory/check determinism path.
4. **Golden fixture**: a generated page asserting a dependency the import facts do
   not show MUST produce a finding.

## Chain-of-trust: every link gets an artifact-based constraint

Discovery/injection/verification chain — and the principle that each link is held by
a constraint verifiable at `codas check` (not by trusting a human/agent to behave):
**process can't be enforced; artifacts can.**

| Link | Silent-failure | Constraint (artifact-based) |
|---|---|---|
| ① human setup | not installed / no hook / no AGENTS.md section | `codas doctor` setup-completeness diagnosis + P0 bootstrap self-check |
| ② AGENTS.md schema layer | missing / drifted / dead command refs | governed doc + `stale_claim` link check + new contract-check (referenced `codas wiki` subcommands exist, points to real CONTRACT.md); Codas self-maintains via `--write` |
| ③ agent grounds (emit-pack) | agent skips grounding, hallucinates | enforce the **artifact** not the process: a generated page must embed `source_inventory_hash` + a nonempty `atlas:claims` block, else `generated_wiki_drift` fires |
| ④ generation | wrong / hallucinated / cherry-picked | `generated_wiki_drift` (bogus claim = error) + `stale_wiki_claim` (existence/authority) |
| ⑤ check runs + gates | nobody runs it / findings ignored | P6 hook gates on `codas check` (pre-commit local + CI unbypassable); `doctor` verifies the hook is installed |

## Acceptance criteria for this decision

- The architecture, invariants, chain constraints, verification design, OSS-backend
  integration model, and the P5 D3 slice plan are recorded in `design.md`.
- The slice plan is consistent with the §8 phase table (P5 deterministic spine; P6
  enforcement hooks; P7 backend adapters) and with codex's corrections (the
  `source_inventory_hash` loop fix; a real `atlas:claims` parser; `app/wiki.py`
  placement; commit generated pages, pack stdout-only; CONTRACT.md outside the
  Trellis-managed AGENTS.md block; bogus-claim = error).

## Non-goals (of this decision task)

- Implementing any slice — D3a–e are separate tasks.
- Picking the default OSS backend now — deferred to P7 (per-backend adapter); P5 is
  backend-agnostic via standard-format grounding.
- MCP — explicitly out of scope; replaced by file-convention + orchestrator wiring.
