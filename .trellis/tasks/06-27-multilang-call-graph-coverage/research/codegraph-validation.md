# CodeGraph Validation

## Summary

Validated CodeGraph 1.1.1 as an advisory multi-language call source for Codas impact.

Decision: P2 can close with advisory CodeGraph coverage. Codas should still keep
compiler/tree-sitter lower-bound call extractors as a separate future track if a
language needs gate-grade calls.

## Real Repository

Repository: `/Users/oydodo/Documents/repo/swift/ciri`

Repo file counts by extension:

| language | files |
| --- | ---: |
| Swift | 4104 |
| Python | 139 |
| JavaScript | 105 |
| Java | 174 |
| YAML | 160 |

CodeGraph index command already run:

```bash
codegraph init /Users/oydodo/Documents/repo/swift/ciri
```

Observed init result: 626 indexed files, 12,755 nodes, 31,362 edges.

`codegraph --version`: `1.1.1`

`project_metadata`:

| key | value |
| --- | --- |
| indexed_with_version | 1.1.1 |
| indexed_with_extraction_version | 24 |

`codegraph status --json` succeeds when run from the repo root and reports:

```json
{
  "initialized": true,
  "version": "1.1.1",
  "projectPath": "/Users/oydodo/Documents/repo/swift/ciri",
  "indexPath": "/Users/oydodo/Documents/repo/swift/ciri/.codegraph",
  "fileCount": 626,
  "nodeCount": 12755,
  "edgeCount": 31362,
  "backend": "node-sqlite",
  "journalMode": "wal",
  "languages": ["python", "swift", "yaml"],
  "index": {
    "builtWithVersion": "1.1.1",
    "builtWithExtractionVersion": 24,
    "currentExtractionVersion": 24,
    "reindexRecommended": false
  }
}
```

`codegraph status --json /Users/oydodo/Documents/repo/swift/ciri` failed under
the Codex sandbox with `Failed to get status: unable to open database file`.
Direct SQLite reads also failed unless opened read-only. Codas now reads
`.codegraph/codegraph.db` directly with SQLite `mode=ro` when present, and uses
`status --json` only as a fallback for non-standard index paths. The fallback tries
the repo-root `codegraph status --json` form first, then the explicit
`codegraph status --json <repo>` form.

## SQLite Schema

Important tables:

```sql
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_at INTEGER NOT NULL,
    indexed_at INTEGER NOT NULL,
    node_count INTEGER DEFAULT 0,
    errors TEXT
);

CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_column INTEGER NOT NULL,
    end_column INTEGER NOT NULL,
    docstring TEXT,
    signature TEXT,
    visibility TEXT,
    is_exported INTEGER DEFAULT 0,
    is_async INTEGER DEFAULT 0,
    is_static INTEGER DEFAULT 0,
    is_abstract INTEGER DEFAULT 0,
    decorators TEXT,
    type_parameters TEXT,
    return_type TEXT,
    updated_at INTEGER NOT NULL
);

CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,
    metadata TEXT,
    line INTEGER,
    col INTEGER,
    provenance TEXT DEFAULT NULL,
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE
);
```

## Indexed Coverage

Indexed files by CodeGraph language:

| language | files |
| --- | ---: |
| swift | 581 |
| python | 35 |
| yaml | 10 |

Node kinds:

| language | main kinds |
| --- | --- |
| swift | method 3393, field 3390, import 1235, enum_member 837, constant 812, struct 772, file 581, enum 342, class 252, component 251, function 144 |
| python | function 317, import 180, variable 86, file 35, method 24, class 6 |

Edge kinds:

| kind | count |
| --- | ---: |
| contains | 11882 |
| calls | 9778 |
| instantiates | 4294 |
| references | 4231 |
| decorates | 540 |
| extends | 381 |
| imports | 238 |
| implements | 18 |

Call-like edge coverage included by Codas: `calls`, `instantiates`.

Call-like edges by language pair:

| pair | edge kind | count |
| --- | --- | ---: |
| swift -> swift | calls | 8882 |
| swift -> swift | instantiates | 4287 |
| python -> python | calls | 725 |
| python -> swift | calls | 170 |
| python -> python | instantiates | 7 |
| swift -> python | calls | 1 |

Codas parsed facts from the Ciri index after path normalization:

- `CodeGraphCallFacts.edges`: 10,531
- `CodeGraphCallFacts.skipped`: 0
- `provenance`: normalized source provider remains `codegraph`
- `resolution`: CodeGraph edge kind, e.g. `calls`, `instantiates`

## Impact Examples

Command:

```bash
PYTHONPATH=/Users/oydodo/Documents/codas/src \
python3 -m codas impact openDocument /Users/oydodo/Documents/repo/swift/ciri
```

Result:

- 2 matched Swift target symbols:
  - `Ciri.App.Router.Router.openDocument`
  - `Ciri.UI.Documents.DocumentListView.DocumentListView.openDocument`
- 24 affected callers across 6 Swift files.
- All displayed affected rows carry `provenance=codegraph`.
- Example affected rows:
  - `[1] Ciri.App.DashboardView.DashboardView.handleSuggestion  Ciri/App/DashboardView.swift  provenance=codegraph resolution=calls`
  - `[1] Ciri.App.DashboardView.DashboardView.openTodayJournal  Ciri/App/DashboardView.swift  provenance=codegraph resolution=calls`
  - `[1] Ciri.UI.Documents.DocumentListView.DocumentListView.documentRow  Ciri/UI/Documents/DocumentListView.swift  provenance=codegraph resolution=calls`
  - `[3] Ciri.App.CiriApp.CiriApp  Ciri/App/CiriApp.swift  provenance=codegraph resolution=instantiates`

JSON output includes `via.source = "codegraph"`, `via.provenance = "codegraph"`,
and `via.resolution` per edge.

CodeGraph's own CLI agreed the target has Swift callers:

```bash
codegraph callers openDocument --json
```

Returned callers included:

- `documentRow` in `Ciri/UI/Documents/DocumentListView.swift`
- `instantiateTemplate` in `Ciri/UI/Documents/DocumentListView.swift`
- `createDocument` in `Ciri/UI/Documents/DocumentListView.swift`
- `handleSuggestion` in `Ciri/App/DashboardView.swift`
- `openTodayJournal` in `Ciri/App/DashboardView.swift`

## Reduced Fixture

Unit tests build a reduced SQLite fixture with:

- JavaScript caller `web/app.js`
- Python callee `src/service.py`
- relative paths, `./` paths, and absolute paths under the repo
- `calls` and `instantiates` edges
- local `.codegraph/codegraph.db` path and status-reported external index path

The tests assert:

- local DB is opened read-only without invoking `codegraph status`
- fallback status `indexPath` is parsed when local DB is absent
- absolute and `./` paths normalize to Codas repo-relative file paths
- method qualified names infer a class for display
- non-Python advisory edges appear in `run_impact()`

## Isolation

CodeGraph remains advisory-only.

Tests cover that CodeGraph facts do not affect:

- inventory JSON bytes/hash behavior
- working snapshots
- `fact_delta()`
- `run_check()` policy inputs
- `codas query calls`
- `codas schema`

`compute_impact()` remains deterministic over in-core `CallFacts`; only
`run_impact()` opts into advisory CodeGraph edges.

## Open-World Gaps

Observed caveats:

- CodeGraph emits some likely false positive cross-language `python -> swift`
  call edges for common names. Codas keeps these advisory and labels provenance.
- CodeGraph indexed Swift/Python/YAML in Ciri, not JavaScript/Java from the repo.
- Dynamic dispatch, overload resolution, protocol/interface dispatch, generics,
  macros, reflection, and inferred receivers remain open-world gaps unless a
  compiler-backed backend or conservative per-language extractor is added.

Recommendation:

- Close P2 with advisory CodeGraph coverage for multi-language `codas impact`.
- Keep P3 SourceKit/indexstore/compiler-backed backend as the next precision track.
- If gate-grade calls are required before P3, create separate in-core tree-sitter
  conservative call extractor tasks per language rather than promoting CodeGraph
  facts into inventory or policies.
