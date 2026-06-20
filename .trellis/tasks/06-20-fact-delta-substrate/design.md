# Design — fact-snapshot + fact-delta substrate (v2-A)

## Goal restated

A `FactSnapshot{symbols, imports, calls}` computable at the working tree OR at `HEAD`,
both **pure functions of (file-set, content)**, plus a pure `diff_snapshots` and
`ScanContext` accessors. No policy change. Byte-identical inventory preserved.

## Module layout

| File | Change | Unit |
|---|---|---|
| `adapters/git.py` | +`list_python_paths_at_head`, +`read_blob_at_head` | codas-adapters |
| `adapters/python_parse.py` | +`parse_sources(sources)` (parse pre-read text) | codas-adapters |
| `adapters/callgraph.py` | package detection: filesystem-stat → file-set-derived (Option A) | codas-adapters |
| `facts/snapshot.py` | NEW — `FactSnapshot`, `snapshot_from_parsed`, `head_snapshot` | codas-facts |
| `facts/delta.py` | NEW — `FactDelta`, `diff_snapshots` (pure) | codas-facts |
| `facts/context.py` | +`working_snapshot()`, `head_snapshot()`, `fact_delta()`; `calls()` drops `repo` arg | codas-facts |

`codas-facts` already imports `codas.structure.index` (`discover_files`,
`workspace_roots`) and the adapters (in `context.py`); `structure.index` imports nothing
from `facts`, so no load-time cycle. The HEAD path reuses the SAME root-filter discipline
as `discover_files` (`structure.index._filter_to_roots`) so the HEAD file set is selected
identically to the working-tree set.

## 1. Reading HEAD (git adapter)

```python
def list_python_paths_at_head(repo) -> tuple[tuple[str, str], ...] | None:
    # git ls-tree -r -z HEAD -> "<mode> <type> <sha>\t<path>" per NUL chunk.
    # Keep type == "blob" and path.endswith(".py"); return ((path, blobsha), ...).
    # None when HEAD does not resolve / not a git repo.

def read_blob_at_head(repo, blobsha) -> str | None:
    # git cat-file blob <sha> -> bytes -> decode("utf-8", errors="ignore").
    # None on failure.
```

- `git ls-tree -r -z HEAD` (full format) gives `mode type sha\tpath`; filtering
  `type == "blob"` drops submodules (`commit`) and (in `-r`) trees, so symlinks (mode
  120000, still a blob) are the only oddity — a `.py` symlink would decode its target
  text; negligible and matches no real source file. Returning the **blob SHA** is
  deliberate: it is exactly the fact-cache (slice 2) key, so this read path is
  cache-ready without rework.
- Decode `utf-8 errors="ignore"` mirrors the working-tree `read_text(errors="ignore")`
  for ASCII/UTF-8 source (this repo). A non-UTF8 file could decode differently than
  `read_text`'s platform default → a spurious delta; documented edge, same one the cache
  design flagged ("key and parse-input consistency"). Out of scope to fully harmonize
  here.
- Per-blob `cat-file` is one process per file (slow). v2-A is "correct, not fast"; the
  cache/batched `cat-file --batch` is the slice-2 optimization. Noted, not done.

## 2. Parsing pre-read sources (python_parse)

```python
def parse_sources(sources: Mapping[str, str]) -> ParsedModules:
    # ast.parse each .py text; SyntaxError/ValueError -> tree=None (skipped).
    # No read_error state: the caller already read the bytes (git read failure is
    # handled upstream, not per-file). Same sort/order as parse_python_modules.
```

`parse_python_modules(repo, files)` is **untouched** (keeps its disk read + OSError
state) — zero byte-identical risk to the working-tree path. `parse_sources` is a sibling
for already-read content (the HEAD path).

## 3. Package detection — the KEY decision (call facts soundness)

`callgraph._module_name(repo, rel)` decides package membership + dotted name by
**statting the working-tree filesystem** (`(repo/rel).parent / "__init__.py").exists()`).
`python.py` already derives both from the **parsed file set** (`package_dirs = {dir of
every __init__.py in the set}` + `_dotted_for`). For a HEAD snapshot built from HEAD
content, filesystem-stat would mix HEAD content with working-tree structure → **unsound**
(e.g. an `__init__.py` added/removed in the working tree but not at HEAD would mislabel
HEAD modules). The snapshot must be a pure function of (file-set, content).

**Option A (RECOMMENDED — unify on file-set-derived):** Refactor `_modules_from_parsed`
to compute `package_dirs` from `parsed.modules` paths (the SAME way `python.py` does) and
replace `_module_name(repo, rel)` with a set-based `_module_name(rel, package_dirs)`:
```python
package_dirs = {dirname(m.path) for m in parsed.modules
                if m.path == "__init__.py" or m.path.endswith("/__init__.py")}
def _module_name(rel, package_dirs):
    if posixpath.dirname(rel) not in package_dirs:
        return None                      # not in a package -> out of scope (same gate)
    # walk up package_dirs collecting basenames; append stem unless __init__  (== _dotted_for)
```
- `extract_call_facts_from_parsed` then no longer needs `repo` → **drop the `repo`
  parameter** (callers: the `extract_call_facts(repo, files)` wrapper, `ScanContext.calls`,
  `snapshot_from_parsed`). This removes callgraph's LAST working-tree filesystem
  dependency → `working_snapshot().calls == inventory["calls"]` from ONE computation (no
  divergence), and is exactly what the cache needs (RawFileFacts pure-content).
- **Byte-identical risk:** changes a determinism-critical wired extractor. Bounded by:
  `python.py` already proves set==filesystem on THIS repo (its set-derived packages feed
  the byte-identical `imports`), and the explicit inventory cross-check
  (`inventory --json` identical before/after) + the 271-test golden net. Reuse `python
  .py`'s `_dotted_for` (extract a shared helper, or duplicate the ~12 lines — but a
  cross-module shared private helper trips `duplicate_implementation`, so EITHER make it
  module-public in one place and import it, OR keep two copies with distinct names).
- **Edge vs legacy:** `_module_name` walked ABSOLUTE paths (`repo/rel`), so an
  `__init__.py` at/above the repo root would pull in out-of-repo directory names; the
  set-based walk is repo-relative and stops at `""`. Strictly MORE correct; on a normal
  repo (no `__init__.py` at repo root) identical. Asserted by the byte-identical check.

**Option B (conservative — opt-in override, working-tree path untouched):** Keep
`_module_name` filesystem-stat as the default (working-tree `calls` byte-identical by
construction); add an optional `package_dirs` arg used ONLY by the HEAD snapshot. Cost:
for the delta to be sound BOTH sides must use the same method, so the delta's
working-tree snapshot must ALSO be computed set-derived — a SECOND computation of
working-tree calls that can differ from `inventory["calls"]` in filesystem-vs-set edge
cases. That divergence (two notions of "working-tree calls") is the reason to prefer A.

**Recommendation: Option A.** It is the correct end-state, unifies callgraph with
python.py, removes the filesystem coupling the cache also needs gone, and the risk is
fully covered by the byte-identical cross-check. Flagging explicitly for codex.

## 4. FactSnapshot + snapshot builders (facts/snapshot.py)

```python
@dataclass(frozen=True)
class FactSnapshot:
    symbols: SymbolFacts
    imports: ImportFacts
    calls: CallFacts

def snapshot_from_parsed(parsed: ParsedModules) -> FactSnapshot:
    return FactSnapshot(
        extract_symbol_facts_from_parsed(parsed),
        extract_import_facts_from_parsed(parsed),
        extract_call_facts_from_parsed(parsed),     # Option A: no repo
    )

def head_snapshot(repo, roots) -> FactSnapshot | None:
    listed = list_python_paths_at_head(repo)
    if listed is None:
        return None
    kept = _filter_to_roots([p for p, _ in listed], roots)      # same discipline as discover_files
    keep = set(kept)
    sources = {p: src for (p, sha) in listed if p in keep
               for src in (read_blob_at_head(repo, sha),) if src is not None}
    return snapshot_from_parsed(parse_sources(sources))
```
(`snapshot.py` imports adapters — allowed in codas-facts. Update `context.py`'s docstring
prose that calls it "the one module outside codas.adapters" → "codas.facts is the seam;
context/snapshot may import adapters." Grep for any other doc/wiki claim asserting the
singular wording and fix — a dogfood moment.)

## 5. FactDelta + diff (facts/delta.py — pure)

Diff on **identity keys**, not whole frozen tuples, so a line shift or a re-resolved
derived field is NOT spurious drift (critical for v2-B couplings — a function moving 3
lines must not fire a coupling):

| Fact | Identity key (diffed) | Dropped (metadata) |
|---|---|---|
| `SymbolFact` | `(module, name, kind)` | `line` |
| `ImportFact` | `(module, target)` | `target_path`, `line` |
| `CallFact` | `(caller_path, caller_class, caller_symbol, callee_path, callee_class, callee_symbol)` | `callee_line`, `caller_line`, `callee_module`, `caller_module`, `resolution` |

(The CallFact key is exactly the existing dedup/sort key in `callgraph`.)

```python
@dataclass(frozen=True)
class FactDelta:
    symbols_added: tuple[tuple[str, str, str], ...]
    symbols_removed: tuple[...]
    imports_added:  tuple[tuple[str, str], ...]
    imports_removed: tuple[...]
    calls_added:    tuple[tuple[str, str, str, str, str, str], ...]
    calls_removed:  tuple[...]
    def is_empty(self) -> bool: ...

def diff_snapshots(base: FactSnapshot, head: FactSnapshot) -> FactDelta:
    # per stream: added = keys(head) - keys(base); removed = keys(base) - keys(head)
    # each returned sorted(); base = HEAD, head = working tree at the call site
```
Pure, deterministic, total-ordered. Returns identity-key tuples (JSON-friendly, and the
unit v2-B couplings match on). Representative facts can be added later if a coupling needs
line/path; keys suffice for set-equality couplings (the policy_registry shape).

## 6. ScanContext accessors

```python
def working_snapshot(self) -> FactSnapshot:
    return FactSnapshot(self.symbols(), self.imports(), self.calls())   # reuse memoized

def head_snapshot(self) -> FactSnapshot | None:
    cache "head_snapshot" -> snapshot.head_snapshot(self.repo, self.roots)

def fact_delta(self) -> FactDelta:
    head = self.head_snapshot()
    base = head if head is not None else _EMPTY_SNAPSHOT
    return diff_snapshots(base, self.working_snapshot())
```
A future policy reads `ctx.fact_delta()` only — stays adapter-free (§11). On a clean tree
(HEAD == working, nothing staged) the delta is empty. When HEAD does not resolve (no
commits), base is empty → everything reads as "added"; the policy layer (v2-B) decides
whether a no-baseline repo is exempt. Snapshots are **policy-time facts** (reflect dirty
state) — like `changed_paths`, they are NOT serialized into `inventory` (byte-identical).

## 7. Determinism / dogfood (load-bearing)

- `inventory --json` and `check` byte-identical before/after (Option A cross-check + the
  existing suite). Snapshots/deltas never enter the inventory.
- `head_snapshot` + `diff_snapshots` deterministic: sorted file list, sorted keys, no
  timestamps, no `Date.now`/random.
- §17 (no LLM); §11 (git reads + extraction behind adapters / the facts seam; no policy
  imports an adapter — this slice adds no policy). New names unique (`FactSnapshot`,
  `FactDelta`, `diff_snapshots`, `snapshot_from_parsed`, `head_snapshot`,
  `list_python_paths_at_head`, `read_blob_at_head`, `parse_sources`) — grep
  `^def`/`^class` to avoid the recurring private-helper-collision trap
  (`duplicate_implementation`).

## 8. Tests

- `parse_sources` parity: `parse_sources({p: disk_text})` ≡ `parse_python_modules` trees
  on a fixture set (same skipped/order).
- Option A equivalence: `extract_call_facts_from_parsed(parsed)` (set-derived) byte-equals
  the pre-refactor output on every fixture + the real repo (`inventory` identical).
- `head_snapshot` on a temp git repo: a committed package → snapshot symbols/imports/calls
  match `snapshot_from_parsed(parse_python_modules(...))` of the same content.
- `head_snapshot` None when no commits / not a repo.
- root filtering: a HEAD `.py` outside the configured roots is excluded from the snapshot.
- `diff_snapshots`: added/removed for each stream; **line-shift ≠ drift** (move a def's
  line, identity-key delta empty); identical snapshots → empty.
- `ScanContext.fact_delta()`: clean tree → empty; stage an added/removed symbol/import/
  call in a temp repo → shows in the delta; no-HEAD → all-added.
- Byte-identical: `inventory --json` 2× equal; `check` 0; full suite green.

## 9. Out of scope (v2-B / slice 2)

Coupling schema, `must_update_if_changed` re-authoring, `drift_couplings` retirement, the
`spec_drift` v2 policy, the persistent cache, `--since` ranges. v2-B gets its own design +
codex review before any gate semantics change.

## 10. Codex design review folds (APPROVE_WITH_CONDITIONS)

**B1 — no partial HEAD snapshot.** If ANY `read_blob_at_head` fails, `head_snapshot`
returns `None` (HEAD unavailable), never a partial snapshot — else an I/O failure on one
file reads as that file's facts being "removed" (false drift). `fact_delta()` treats
`None` HEAD as no-baseline (empty base), the same as no-commits.

**B2 — import delta key keeps `target_path`.** `dependency_direction` consumes
`target_path` as semantic evidence (first-party target path), so v2-B import couplings
need it. Import identity key = **`(module, target, target_path)`** (drop only `line`).
Within one snapshot `(module, target)` already determines `target_path`, so this does not
change intra-snapshot cardinality; across HEAD↔working it makes a first-party↔external
resolution flip show as removed+added (wanted).

**B3 — decode alignment.** The working-tree parse currently reads
`read_text(errors="ignore")` with the platform-default codec — a latent cross-machine
nondeterminism. Pin BOTH paths to explicit **`utf-8`, `errors="ignore"`**:
`parse_python_modules` reads `path.read_bytes().decode("utf-8", "ignore")`; the HEAD blob
decodes the same way. This is a determinism IMPROVEMENT (removes the locale dependency);
byte-identical on this UTF-8/ASCII repo (cross-check the `f47ed0c…` inventory hash). The
slice-1 OSError test mocks `read_text` → re-point it at `read_bytes`. `.py` symlink blobs
(git stores link text; `read_text` follows the link) remain a documented parity edge,
negligible for real source.

**Q2 — shared dotted-name helper.** Expose `package_dirs(py_files) -> set[str]` and
`dotted_for(rel, package_dirs) -> str` as **module-public** in `adapters/python.py`;
`callgraph` imports them (both in `codas-adapters`, intra-unit). One definition imported —
NOT two distinct-named copies (which would dodge `duplicate_implementation` while keeping
the duplication). `callgraph._module_name(rel, pkg_dirs)` = `None` when
`posixpath.dirname(rel) not in pkg_dirs` else `dotted_for(rel, pkg_dirs)`.

**Should-1 — divergence fixtures.** Add fixtures for the set-vs-filesystem divergence
cases: deleted-tracked `__init__.py`, ignored/excluded `__init__.py`, workspace root
inside a package, repo-root `__init__.py`. Each asserts the set-derived `_module_name`
behavior (and that the real-repo inventory stays byte-identical).

**Should-2 — public root filter.** Add public `filter_to_roots(files, roots)` to
`structure.index` (delegate `_filter_to_roots` to it); the facts layer calls the public
name, never the underscore.

**Nit-1 — docstring.** Update `context.py:56-60` singular "the one place outside
codas.adapters permitted to import an adapter" → "codas.facts is the seam; its modules
(context, snapshot) may import adapters."

**Nit-2 — sort HEAD lists.** Sort the HEAD path list explicitly after parsing `ls-tree`
(don't rely on git tree order) — determinism local to Codas.

## 11. Codex impl review fold (REWORK → fixed)

**Blocker — deleted-tracked `__init__.py` crash.** A tracked `__init__.py` deleted from
the working tree is still listed by `git ls-files --cached`, so it enters the scan as a
`read_error` module. The first cut derived `package_dirs_of` from ALL module paths, so it
marked that directory a package → `_modules_from_parsed` re-raised the `read_error` →
crash on a dirty consumer repo (the legacy filesystem walk saw `.exists() == False` and
dropped the package). **Fix:** gate package detection on read success —
`package_dirs_of([m.path for m in parsed.modules if m.read_error is None])`. `read_error
is None` is the content-pure proxy for the old `.exists()` gate: deleted/unreadable
`__init__.py` no longer marks a package; readable-but-unparseable still does (it exists);
HEAD blobs always read so no change; an unreadable NON-`__init__` in-scope package file
still re-raises (OSError divergence preserved). Clean-repo byte-identical preserved (a
clean tree has no `read_error` modules). Pathological edge — a permission-denied
`__init__.py` that exists but can't be read is treated as not-a-package; accepted/documented.

**Shoulds — coverage.** Added `test_deleted_tracked_init_drops_package_without_crashing`
(exercises the REAL `discover_files`/git-cached path, not a manual tuple omission) and
`test_repo_root_package_dotted_name_is_repo_relative`. 24 substrate tests, 328 total,
check 0, inventory deterministic, wiki --verify clean.
