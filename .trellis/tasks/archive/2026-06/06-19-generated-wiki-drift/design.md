# Design — D3d generated_wiki_drift policy

## 1. Components (§11-clean)

```
adapters/wiki.py   extract_generated_claims(repo, files, generated_root)  (NEW parser)
facts/context.py   ScanContext.generated_claims()                          (seam, memoized)
policies/generated_wiki_drift.py  check_generated_wiki_drift(ctx)          (consumes facts)
app/check.py       findings.extend(check_generated_wiki_drift(ctx))        (wiring)
.codas/policies.yml  generated_wiki_drift: error                           (declaration)
```

The policy imports `codas.facts.context` + `codas.structure.loader` +
`codas.structure.program_loader` + `codas.core` — NO adapter (dependency_direction
stays green). Parsing the `atlas:claims` fence is the adapter's job.

## 2. Parser — `extract_generated_claims` (adapters/wiki.py)

```python
@dataclass(frozen=True)
class GeneratedClaim:
    source: str
    line: int
    kind: str       # "unit" | "roadmap"
    subject: str
    value: str

@dataclass(frozen=True)
class GeneratedPage:
    source: str
    source_inventory_hash: str   # "" if absent
    claims: tuple[GeneratedClaim, ...]
    has_block: bool

@dataclass(frozen=True)
class GeneratedClaims:
    pages: tuple[GeneratedPage, ...]
    skipped: tuple[str, ...]

def extract_generated_claims(repo, files, generated_root=".codas/wiki/generated") -> GeneratedClaims:
```

Parse, per `.md` under `generated_root`:
- Walk lines; OUTSIDE a block, a line whose stripped form starts with ```` ``` ```` and
  whose info string is exactly `atlas:claims` opens the block (`has_block = True`).
  Inside, a ```` ``` ```` line closes it.
- Inside the block:
  - `source_inventory_hash: <h>` → `source_inventory_hash = <h>` (first one wins).
  - `unit: <subject> -> <value>` / `roadmap: <subject> -> <value>` → a `GeneratedClaim`
    (split on the first `": "` for the kind, then partition on `" -> "`; skip a line
    lacking ` -> `).
- This is the deliberate INVERSE of `extract_wiki_claims` (which skips fences) — two
  extractors, opposite fence handling, same module.
- Deterministic: pages sorted by source; claims in file order; skipped sorted.

Reuse the existing fence convention: a fence line is `stripped.startswith("```")` (the
wiki/markdown adapters use the same). Info-string match: `stripped[3:].strip() ==
"atlas:claims"`.

## 3. ScanContext accessor

```python
def generated_claims(self) -> GeneratedClaims:
    if "generated_claims" not in self._cache:
        root = (self.config.raw.get("wiki") or {}).get("path", ".codas/wiki").rstrip("/") + "/generated"
        self._cache["generated_claims"] = extract_generated_claims(self.repo, self.files, root)
    return self._cache["generated_claims"]
```

Re-export `GeneratedClaim`/`GeneratedPage`/`GeneratedClaims` via `__all__` (the facts
vocabulary). **Not** serialized into inventory (policy-time fact; like spec_drift's
changed_paths — keeps inventory byte-identical / avoids a generated-page→inventory loop
concern entirely since it never enters inventory).

## 4. Policy — `check_generated_wiki_drift(ctx)`

```python
def check_generated_wiki_drift(ctx) -> list[Finding]:
    gen = ctx.generated_claims()
    if not gen.pages:
        return []
    units = _unit_paths(ctx.repo)        # {id: path} via load_structure_map; {} on error
    statuses = _work_item_status(ctx.repo)  # {id: status} via load_program_plan; {} on error
    findings = []
    for page in gen.pages:
        if not (page.has_block and page.source_inventory_hash and page.claims):
            findings.append(error: "generated page must embed a nonempty atlas:claims "
                            "block with a source_inventory_hash" ; evidence=page.source)
            continue
        for c in page.claims:
            if c.kind == "unit":
                if c.subject not in units:
                    findings.append(error: f"claims unknown structure unit '{c.subject}'")
                elif units[c.subject] != c.value:
                    findings.append(error: f"claims unit '{c.subject}' path '{c.value}' "
                                    f"but the Structure Map says '{units[c.subject]}'")
            elif c.kind == "roadmap":
                if c.subject not in statuses:
                    findings.append(error: f"claims unknown work item '{c.subject}'")
                elif statuses[c.subject] != c.value:
                    findings.append(error: f"claims work item '{c.subject}' status "
                                    f"'{c.value}' but the Program Plan says '{statuses[c.subject]}'")
    findings.sort(key=(source, line, message))
    return findings
```

- `check_id = "generated-wiki-drift"`, severity `error`. Evidence
  `Evidence(path=page.source, line=claim.line, detail=...)`.
- Load failures (`StructureMapError`/`ProgramPlanError`) → `{}` (other policies own those
  load-error findings); a claim then resolves against an empty map → "unknown unit/work
  item" error, which is acceptable (a broken structure map is already an error elsewhere;
  but to avoid a noisy cascade, if the loader raised, SKIP the corresponding claim kind
  rather than flag every claim unknown — return `None` sentinel vs `{}` and skip). Decide
  in review (open Q1).
- Deterministic total-key sort.

## 5. Wiring

`app/check.py`: `findings.extend(check_generated_wiki_drift(ctx))` after
`check_spec_drift`. `.codas/policies.yml`: add `generated_wiki_drift: severity: error,
description: ...`. `test_codas_check.py::test_scan_context_built_once...`: add
`mock.patch("codas.app.check.check_generated_wiki_drift", return_value=[])` to the
patch set + spy tuple (the recurring ctx-consumer trap).

## 6. Tests (`tests/test_generated_wiki_drift.py`)

Build a `ScanContext` over a temp repo with a `.codas/structure.yml` + `.codas/program.yml`
+ a `.codas/wiki/generated/page.md`, or inject `ctx._cache["generated_claims"]` + write
the structure/program files. Golden fixtures:
- correct page (claims match units/program) → 0.
- bogus `unit: x -> wrongpath` → 1 error (mismatch); unknown unit id → 1 error.
- `roadmap: id -> wrongstatus` → error; unknown work item → error.
- page with no `atlas:claims` block → error; block present but no `source_inventory_hash`
  → error; empty claims → error.
- `extract_generated_claims` unit tests: parses hash + unit + roadmap lines; ignores a
  non-atlas fence + prose; `has_block` false when absent; deterministic.
- Real repo: `run_check(cwd)` has no `generated-wiki-drift` finding (committed
  governance.md verifies clean) — the dogfood guard.

## 7. Determinism / dogfood

- `generated_claims` is a policy-time fact, NOT in inventory → `inventory --json`
  byte-identical, no generated-page→inventory hash interaction.
- Committed governance.md: its `unit:`/`roadmap:` claims match current structure/program
  (unchanged since generation) → 0 errors. The stale `source_inventory_hash` is NOT
  compared in check → no warning. So `codas check .` stays 0 without regenerating.
- New names: `extract_generated_claims`, `check_generated_wiki_drift`, `_unit_paths`,
  `_work_item_status`, `GeneratedClaim`/`GeneratedPage`/`GeneratedClaims` — grep unique.

## 8. Open questions for review

1. Loader-failure handling: skip the claim-kind whose loader raised (avoid a cascade of
   "unknown unit" errors when structure.yml is itself broken — already flagged by
   structure_map_loads/program_plan), vs flag. Leaning: skip (sentinel `None` from the
   helper → skip that kind). Confirm.
2. Should a generated page with `has_block` but ZERO recognized claims (only a hash) be
   an error? Design link ③ says "nonempty atlas:claims block". Leaning: yes, require ≥1
   claim. Confirm.
3. Multiple `atlas:claims` blocks in one page — union all, or only the first? Leaning:
   union (defensive). Confirm.
4. Is `error` right for a structural-missing-block (vs warning)? Design §3 link ③ makes
   the grounding-proof a hard requirement for generated pages → error. Confirm.
