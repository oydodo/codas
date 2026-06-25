# Design - Problem-3 anchors + RepairTarget

Status: review-corrected design, ready for implementation planning review.
Grounding: current code at `main@bf08cb5`, task PRD, and codex adversarial review on
2026-06-25.

## 1. Current State

`code_anchor` currently reads structural claims only from `.codas/wiki/code/**` through
`ScanContext.code_anchor_claims()` and `extract_semantic_claims()`. The parser supports Markdown
fences carrying `defines:`, `calls:`, and `contains:` claims. Malformed lines are skipped because
the corpus is advisory.

`fact_coupling` currently reads only `.codas/claims.yml fact_couplings`. It gates on
`ctx.fact_delta()` and `ctx.changed_paths()`: a watched deterministic fact appears or disappears,
and a required companion path must co-change in the same working-tree diff.

`Finding.meta` can already carry structured JSON, but console rendering ignores it. Preflight
builds a context pack, but it does not surface repair targets.

Current deterministic Python symbol facts contain top-level classes and functions only. They do
not include constants such as `WORLD_BY_FAMILY`.

## 2. Invariants

1. `code_anchor` remains warning-only. A broken anchor is open-world evidence, never a blocking
   contradiction.
2. `fact_coupling` remains the only blocking surface for this feature.
3. Blocking decisions depend only on deterministic fact-delta presence plus changed paths.
4. Blocking decisions never depend on whether an anchor resolves, whether `code_anchor` warned, or
   what RepairTarget guessed.
5. RepairTarget is metadata and presentation only. It never changes whether a finding exists.
6. `.codas/wiki/code/**` remains advisory-only forever.
7. Archived Trellis tasks and workspace journals are never anchor-bearing, even if a config glob
   matches them.
8. Syntax examples in live docs must not become active anchors.

## 3. Config Surface

Add a top-level config section:

```yaml
anchors:
  live_documents:
    - docs/codas-design.html
    - docs/codas-implementation-plan.html
    - .trellis/tasks/*/prd.md
    - .trellis/tasks/*/design.md
```

Semantics:

- `anchors.live_documents` is a list of repo-relative files or globs.
- Default is `[]`.
- It is independent of `constraint_sources`.
- `.codas/wiki/code/**` is still an implicit advisory corpus.
- Configured live docs are both advisory anchor sources and eligible gate-declaration sources.
- `implement.md` is intentionally excluded initially.

Validation:

- Each configured entry must match at least one scanned, non-excluded file.
- Unsupported extensions are errors. Initial support is `.md` and `.html`.
- Matches under `.trellis/tasks/archive/**` or `.trellis/workspace/**` are ignored, and if an
  entry matches only ignored files it is treated as empty.
- Config validation findings must be deterministic and include the config path plus entry text.

## 4. Anchor Parsing

### Markdown

Active claims use the existing fenced form:

````text
```atlas:claims
defines: concept -> src/pkg/mod.py::::name
calls: src/pkg/a.py::::f -> src/pkg/b.py::::g
contains: src/pkg/mod.py
```
````

Parser correction required:

- An `atlas:claims` fence inside another fenced code example is not active.
- Four-backtick examples that show a three-backtick `atlas:claims` fence must not parse as active
  claims.
- Unterminated active claim fences in live docs are malformed live-doc anchor errors.

This can be implemented by a small Markdown fence scanner that tracks outer fences by backtick
length and only treats a fence as active when it is a top-level fence whose info string is exactly
`atlas:claims`.

### HTML

HTML claims use:

```html
<pre data-atlas-claims>
contains: src/codas/facts/openworld.py
defines: open-world registry accessor -> src/codas/facts/openworld.py::::world_of
</pre>
```

Only `<pre>` start tags carrying `data-atlas-claims` are active. Ordinary `<pre>` examples remain
ignored by stale HTML path extraction and by anchor parsing.

## 5. Fact Seam

Add two accessors:

1. `ScanContext.code_anchor_claims()`
   - advisory corpus
   - source set: `.codas/wiki/code/**` plus configured live docs
   - consumed by `code_anchor`
   - never serialized into inventory

2. `ScanContext.live_doc_anchor_claims()`
   - strict corpus
   - source set: configured live docs only
   - consumed by `fact_coupling` and preflight repair surfacing
   - never serialized into inventory
   - preserves malformed records

Use one shared parser model with a strictness flag rather than duplicating grammar. Code-wiki mode
keeps permissive skip behavior. Live-doc mode preserves malformed records so `fact_coupling` can
emit hard-gate errors.

## 6. RepairTarget

`code_anchor` warnings for non-resolving claims gain `meta.repair_target`:

```json
{
  "repair_target": {
    "stale_span": {
      "path": "docs/codas-design.html",
      "line": 845,
      "claim_kind": "defines",
      "detail": "src/codas/facts/openworld.py::::world_of"
    },
    "old_node": {
      "kind": "symbol",
      "value": "src/codas/facts/openworld.py::::world_of"
    },
    "best_match_new_node": {
      "kind": "symbol",
      "value": "src/codas/facts/openworld.py::::world_for"
    },
    "action": "retarget-subject-node"
  }
}
```

Best-match uses only deterministic fact delta:

- For a broken `defines:` claim, match a removed `(module, name, kind)` and rank added symbols by
  same module, same kind, then deterministic string similarity.
- For a broken `calls:` claim, match a removed edge and rank added edges with one endpoint stable.
- For module-path `contains:`, emit no repair target.
- If no candidate clears a fixed threshold, `best_match_new_node` is `null`.

Presentation requirements:

- `codas check --json` includes `meta.repair_target`.
- Human `codas check` output prints a short repair line when present.
- Preflight context pack includes a capped `repair_targets` section.
- SessionStart preflight is secondary. Failed `codas check` output is the primary commit-time
  repair carrier.

## 7. Anchor-Derived Fact Couplings

`fact_coupling` gets two coupling sources:

1. Manual `.codas/claims.yml fact_couplings`.
2. Derived couplings from `ScanContext.live_doc_anchor_claims()`.

Derived coupling eligibility:

- source is a configured live doc
- claim parsed cleanly
- shape is one of the eligible shapes below
- source path is not excluded

Eligible shapes:

- `defines: concept -> src/a.py::::f`
  - derives `symbol_added` and `symbol_removed` watchers for exact `(module, name, kind)` when
    the target can be mapped to deterministic symbol fact identity
  - required companion path is the source doc
- `calls: caller -> callee`
  - derives `call_added` and `call_removed` watchers for exact call identity
  - required companion path is the source doc
- `contains: src/a.py`
  - derives public top-level `symbol_added` and `symbol_removed` watchers under that file
  - public means symbol name does not start with `_`
  - required companion path is the source doc

Non-eligible shapes remain advisory-only:

- `contains:` directory/package nodes
- method-node `contains:`
- all `.codas/wiki/code/**` claims
- anchors for facts not emitted by deterministic extractors

Malformed live-doc anchor records produce `fact-coupling` errors because a hard-gate declaration
must not silently disable itself.

Manual and derived couplings are normalized into one obligation set. Deduplicate by watched-delta
identity plus required path. If manual and derived obligations collide, emit one finding and prefer
manual owner/reason metadata.

## 8. Dogfood Migration

Add `anchors.live_documents` to `.codas/config.yml`:

- `docs/codas-design.html`
- `docs/codas-implementation-plan.html`
- `.trellis/tasks/*/prd.md`
- `.trellis/tasks/*/design.md`

Replace the existing openworld manual rows in `.codas/claims.yml` with anchors in
`docs/codas-design.html` section 9.4:

- `contains: src/codas/facts/openworld.py`
- `defines: open-world registry accessor -> src/codas/facts/openworld.py::::world_of`
- `defines: open-world gap manifest -> src/codas/facts/openworld.py::::open_world_gaps`

Do not anchor `WORLD_BY_FAMILY` unless this task explicitly expands deterministic symbol facts to
module constants with tests. Current extractor does not emit constants.

The module-path `contains:` anchor preserves the current public symbol add/remove coverage for
`openworld.py`. The fine `defines:` anchors provide targeted stale-anchor warnings and
RepairTargets for renamed functions.

## 9. File Surface

Primary code:

- `src/codas/config/loader.py`
- `src/codas/adapters/semantic.py`
- `src/codas/adapters/html.py` or a new anchor parser module under `src/codas/adapters`
- `src/codas/facts/context.py`
- `src/codas/policies/code_anchor.py`
- `src/codas/policies/fact_coupling.py`
- `src/codas/app/preflight.py`
- `src/codas/reporting/console.py`

Dogfood/config/docs:

- `.codas/config.yml`
- `.codas/claims.yml`
- `.codas/policies.yml`
- `.codas/program.yml`
- `docs/codas-design.html`

Tests:

- `tests/test_code_anchor.py`
- `tests/test_fact_coupling.py`
- `tests/test_preflight.py`
- `tests/test_codas_check.py` or console output coverage
- parser-focused tests for Markdown examples and HTML active blocks

## 10. Test Plan

Anchor corpus tests:

- live Markdown doc is scanned
- live HTML `<pre data-atlas-claims>` is scanned
- archived task doc is ignored
- workspace journal is ignored
- four-backtick Markdown syntax example does not parse as active anchor
- unterminated live-doc claim block emits malformed declaration finding
- code-wiki malformed lines remain tolerant skips
- live-doc anchors remain out of inventory/hash
- empty/misspelled live-doc glob emits deterministic finding

RepairTarget tests:

- rename of a live-doc `defines:` target produces warning with `best_match_new_node`
- warning remains warning
- no matching delta produces warning with `best_match_new_node=null`
- console output includes repair target
- JSON output includes `meta.repair_target`
- preflight pack and human summary include capped repair targets

Fact-coupling tests:

- live-doc `defines:` anchor derives exact symbol add/remove obligations
- live-doc `calls:` anchor derives exact call add/remove obligations
- live-doc file-path `contains:` derives public symbol add/remove obligations
- private symbol change under file-path `contains:` does not fire
- directory/package/method `contains:` does not derive a gate
- broken anchor alone without matching deterministic delta does not produce a gate error
- malformed live-doc anchor produces gate error
- manual and derived equivalent obligations dedupe
- `.codas/wiki/code/**` claims never derive gates

Dogfood validation:

- remove openworld manual rows from `.codas/claims.yml`
- add replacement anchors to `docs/codas-design.html`
- `PYTHONPATH=src python3 -m unittest`
- `PYTHONPATH=src python3 -m codas check .`
- `PYTHONPATH=src python3 -m codas wiki --verify .`
- `PYTHONPATH=src python3 -m codas agents --verify .`

## 11. Open Choices

Keep this task narrow: do not add constant symbol facts unless implementation shows dogfood needs
them. The current design can preserve openworld coverage with `contains: src/codas/facts/openworld.py`
plus function anchors.
