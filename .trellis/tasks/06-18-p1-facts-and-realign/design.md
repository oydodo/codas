# Design — P1 doc claim index, task facts and trellis_context realign

Mirrors the shipped loaders/inventory (commits 413c50f, 6a1acc2). Revised after
codex review of v1 (markdown robustness + half-done realign).

## New module: `src/codas/adapters/`

Plan §5 names Markdown Adapter and Trellis Adapter as distinct modules. Create
`src/codas/adapters/{__init__,markdown,trellis}.py`; register a `codas-adapters`
unit in `.codas/structure.yml` (the loaded Structure Map — not a root
`structure.yml`).

### Markdown adapter (`adapters/markdown.py`)

`extract_doc_claims(repo, files) -> list[DocClaim]`, `files` = the discovered
repo file list (`structure.index.discover_files`). Scan only governance/doc
Markdown: `*.md` NOT under `.trellis/tasks/` or `.trellis/workspace/`.

Per file, line by line, **fence-aware** (toggle on lines matching ``^\s*(```|~~~)``;
skip lines inside a fence). For each non-fenced line collect candidates:

- Inline links/images `(!?)\[[^\]]*\]\(([^)]+)\)`. If group 1 is `!` → image,
  skip. Else destination = group 2; parse out the optional title by taking the
  text before the first unescaped space, then strip surrounding `<>`.
- Backtick code spans `` `([^`]+)` ``.

**Normalize-first pipeline** (same for both kinds, so fragments are reachable):
1. strip; drop if it contains `://`, or starts with `#` or `mailto:`.
2. split off a `#fragment` (keep the path part, preserve fragment separately for
   future P2 anchor checks); drop if the path part is empty.
3. path-shape gate:
   - links: accept a relative path that has a known extension OR a `/`.
   - backtick spans: stricter — require `/` **and** a known extension
     (`.md .py .html .yml .yaml .json .toml .txt`) to limit prose noise.
4. reject if it still contains whitespace or doesn't match `^[\w./#-]+$`
   (post-fragment, `#` already removed).
5. `exists = (repo / path).exists()`.

Reference-style links (`[text][id]` + `[id]: path`) are **out of scope** for P1
(tested as intentionally ignored). De-duplicate; sort by `(source, line, path)`.

```python
@dataclass(frozen=True)
class DocClaim:
    source: str       # repo-relative .md path
    line: int
    path: str         # referenced repo-relative path (no fragment)
    fragment: str     # "" or the stripped #anchor (for future P2)
    kind: str         # "link" | "code"
    exists: bool
```

Residual noise (path-shaped example strings in inline prose, e.g. a dialogue
`` `src/ui/Composer.tsx` ``) is accepted and bounded by fence-skipping + the
strict backtick gate; it is signal for P2 `stale_claim`, not a finding here.

### Trellis adapter (`adapters/trellis.py`)

`extract_task_facts(repo, config) -> TaskFacts`. Scan
`<workflow_root>/tasks/**/task.json` (active + `archive/`); this is a superset of
config `workflow_task_globs` and is documented as the chosen source.

Per `task.json`: `json.loads`. On JSON / type error, record the repo-relative
path in `skipped` (do not raise — inventory must not hard-fail on a stray file).
Otherwise emit:

```python
@dataclass(frozen=True)
class TaskFact:
    id: str            # task.json "id" or "name", coerced to str, else dir name
    status: str        # coerced to str, default ""
    package: str | None
    dev_type: str | None
    priority: str | None
    archived: bool     # "archive" in task_json.relative_to(tasks_root).parts

@dataclass(frozen=True)
class TaskFacts:
    items: tuple[TaskFact, ...]   # sorted by (archived, id)
    skipped: tuple[str, ...]      # malformed task.json paths, sorted
```

All sort keys are coerced to `str` first (no `None`/non-string in sort tuples).

## Inventory (`structure/inventory.py`, extended)

`build_inventory` already calls `build_artifact_index`, which calls
`discover_files`. Refactor so `build_inventory` calls `discover_files` once and
passes the list to BOTH `build_artifact_index` and `extract_doc_claims` (avoids a
second walk and keeps file discovery single-sourced). Add two siblings (flat §5
keys untouched; deterministic; with provenance):

```json
"doc_claims": {
  "sources": ["README.md", "CONTEXT.md", "..."],
  "references": [
    {"source": "README.md", "line": 7, "path": "docs/codas-design.html",
     "fragment": "", "kind": "link", "exists": true}
  ]
},
"tasks": {
  "source_root": ".trellis/tasks",
  "items": [
    {"id": "p1-facts-and-realign", "status": "in_progress", "package": "codas",
     "dev_type": null, "priority": "P2", "archived": false}
  ],
  "skipped": []
}
```

## trellis_context realign (`policies/trellis_context.py`)

Trellis 0.6.2: PRD-only tasks are valid; implement/check.jsonl are conditional.
- `REQUIRED_TASK_FILES = ("task.json", "prd.md")`.
- **Remove the `trellis-task-glob-missing` check entirely** (it errored when
  config omitted implement/check.jsonl globs — requiring discovery globs for
  now-optional files is the other half of the same stale assumption). Keep
  `trellis-tasks-root-missing`.
- Update the `trellis-task-context-missing` recommendation to drop the removed
  `init-context` wording (point at `task.py add-context` / PRD).

## Registration (`.codas/structure.yml`)

New unit + `codas-source.allowed_children`:
```yaml
codas-adapters:
  path: src/codas/adapters
  kind: adapters_module
  owner: Codas Core
  purpose: Markdown and Trellis adapters extracting doc claims and task facts for the Atlas inventory.
  canonical_placement: Source/format adapters belong under src/codas/adapters.
  status: active
  must_update_if_changed:
    - docs/codas-implementation-plan.html
```
Dependency check: `codas-source` already `may_depend_on: trellis-workflow`, so a
Trellis adapter under it is allowed; the forbidden dep is `role-integrations`,
untouched.

## Tests (`tests/test_adapters.py`, + inventory/trellis_context)

Markdown (each its own fixture, asserting normalized path + exists + skip):
- plain link to an existing + a missing path; titled link `[t](p "x")` → `p`;
  image `![a](p)` skipped; reference-style `[t][id]`/`[id]: p` ignored;
  fenced-code block contents skipped; http/anchor/mailto skipped; backtick path
  with `#fragment` → path + fragment split; prose backtick word (no `/`/ext)
  ignored; a ref under `.trellis/tasks/` not scanned.
- determinism: extract twice → identical.

Trellis:
- active + archived tasks → facts with correct `archived`/status; malformed
  task.json → in `skipped`, not raised, not in items; null package/dev_type sort
  without error.

Inventory: `doc_claims` + `tasks` blocks present, deterministic (build twice →
identical).

trellis_context: task with only task.json + prd.md → no
`trellis-task-context-missing`; missing prd.md → warning; missing
implement/check.jsonl → no warning; config without implement/check globs → no
`trellis-task-glob-missing` (check removed).

## Determinism / scope notes

- Every emitted list sorted by stable string keys; no timestamps; byte-identical
  across runs.
- Markdown extraction is conservative; index-only (no findings). The
  `stale_claim` policy that consumes `exists=false` refs is P2.
- Malformed task.json is non-fatal but **visible** via `tasks.skipped`.
