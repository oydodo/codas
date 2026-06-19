# Design — spec_drift v0 (diff-grounded, materiality-as-claim)

## 1. Decision record: direction + the materiality wall

Codex review of the first draft (which read `must_update_if_changed` as
"docs→unit") was correct to call it BACKWARDS. The authoritative schema
(`docs/codas-structure-map-schema.html` §4) defines the field as *"Docs, specs, wiki
pages or config files that should change **when this unit changes materially**"* —
**unit change = trigger; listed paths = required reactions; obligation scoped to
material changes.**

"Material" is semantic; the correctness core may not judge it (§17). The naive
deterministic proxy ("any edit = material") is both unfaithful and self-defeating:
implementing this policy edits `src/codas/policies` + `src/codas/app`, which would then
demand a same-commit edit of `docs/codas-implementation-plan.html` (codex BLOCKER).

User's reframing fixes the foundation: Codas's "changed" notion is hash/file-level
(binary). Materiality needs the **diff** plus a **judgment**. Therefore split into:

- coarse `must_update_if_changed` → **advisory** (not gating; not built in v0).
- vouched **drift coupling** (materiality judged by agent/human) → **gating**, verified
  deterministically against the diff.

> Codas grounds (diff) · host agent judges (material?) · Codas verifies (reaction
> present?). The wiki engine-split, applied to drift.

## 2. Components

```
adapters/git.py        extract_changed_paths(repo) -> tuple[str,...]   (diff substrate)
facts/context.py       ScanContext.changed_paths()                      (memoized seam)
policies/spec_drift.py check_spec_drift(ctx)                            (claim verifier)
.codas/claims.yml      drift_couplings: [...]                           (vouched rules; empty live)
app/check.py           findings.extend(check_spec_drift(ctx))          (wiring)
```

## 3. Git adapter (`src/codas/adapters/git.py`)

```python
def extract_changed_paths(repo: Path) -> tuple[str, ...]:
    """Working-tree paths differing from HEAD (tracked diff ∪ untracked).

    Repo-relative posix, sorted, de-duplicated. () when git is absent, the path is
    not a repo, or HEAD does not resolve (no baseline → no drift to compute).
    Deterministic given the current tree state. NOT part of `inventory` (dirty-state
    fact; would break the byte-identical inventory invariant)."""
```

- `git -C <repo> diff -z --name-only --no-renames HEAD` → tracked add/modify/delete vs
  HEAD (staged + unstaged). `-z` → NUL-delimited (filenames with spaces/newlines safe,
  codex SHOULD). `--no-renames` → deterministic add/delete pairs.
- `git -C <repo> ls-files -z --others --exclude-standard` → untracked new files.
- Split each on `\0`, drop empties, normalize `\`→`/`, `sorted(set(...))`.
- `except (CalledProcessError, FileNotFoundError): return ()` — mirrors
  `structure.index._git_files`. A no-HEAD repo makes `diff HEAD` exit non-zero → `()`.
- An empty-repo / detached edge cannot make output non-deterministic: order is imposed
  by `sorted`, not git.

Adapter + seam (not raw subprocess in the policy): git is an ecosystem fact source;
keeping extraction in `codas.adapters` + exposing via `ScanContext` keeps the policy a
pure fact-consumer (§11) and lets P6 hooks reuse the diff fact. `dependency_direction`
stays green (the policy imports `codas.facts`/`codas.config`, never `codas.adapters`).
Codex confirmed this seam (changed_paths in the facts layer but excluded from
`inventory`) is the correct §11 + determinism shape.

## 4. ScanContext seam

```python
def changed_paths(self) -> tuple[str, ...]:
    """Working-tree paths differing from HEAD (cached; git adapter). Policy-time
    fact; deliberately not serialized into inventory."""
    if "changed_paths" not in self._cache:
        self._cache["changed_paths"] = extract_changed_paths(self.repo)
    return self._cache["changed_paths"]
```

Import `extract_changed_paths` from `codas.adapters.git`. `inventory.py` is **not**
touched — proving changed_paths never enters the hashed inventory.

## 5. Policy (`src/codas/policies/spec_drift.py`)

```
claims_doc = load_claims(ctx.repo / ".codas/claims.yml")   # graceful: missing file -> {}
couplings  = claims_doc.get("drift_couplings") or []
changed    = ctx.changed_paths()
if not changed: return []                                   # clean tree -> 0

for idx, c in enumerate(couplings):                         # stable order = file order
    when = c.get("when_changed"); requires = c.get("requires") or []
    if not when or not _any_match(changed, when): continue  # change site absent -> dormant
    for req in requires:
        if not _any_match(changed, req):
            emit finding(when, req, owner, reason)
findings.sort(key=(when_changed, requirement, message))
```

- `_any_match(paths, pattern)` = `any(fnmatch(p, pattern) or p == pattern for p in
  paths)` — glob-aware (couplings may use `src/codas/policies/**` etc.).
- Malformed entries (missing `when_changed`) are skipped, not crashes. If `claims.yml`
  fails to load, surface a single load-error finding (mirror
  `duplicate_implementation`'s `ConfigLoadError` handling) — but `load_claims` on a
  valid file with no `drift_couplings` returns the dict with the key absent → `[]`.
- **Finding**: severity `error`, `check_id="spec-drift"`; message names the change site
  and the missing required reaction; evidence `Evidence(path=".codas/claims.yml",
  detail=f"drift_couplings[{when}] -> {req}")`; recommendation: update the required
  reaction in the same change, or revise/justify the coupling. `meta={"when_changed",
  "requires": req, "owner"}`.
- Deterministic: couplings iterated in file order, findings total-key sorted.

## 6. claims.yml extension

Add an optional top-level `drift_couplings:` list alongside `duplicate_relationships`.
No loader change needed — `load_claims` returns the whole mapping; spec_drift reads the
new key, duplicate_implementation reads its own. The **live repo ships with no
`drift_couplings`** → spec_drift returns `[]` on `check .` → resting gate stays 0.
Couplings are authored as genuinely-material couplings are discovered (opt-in, vouched).

## 7. Orchestration wiring

`app/check.py`: `findings.extend(check_spec_drift(ctx))` after `check_stale_wiki_claim`.
`test_codas_check.py::test_scan_context_built_once_and_forwarded_to_policies`: add
`mock.patch("codas.app.check.check_spec_drift", return_value=[])` and include the spy in
the one-ctx-forwarded assertion tuple (handoff pitfall: every ctx-consuming policy must
be patched there).

## 8. Tests (`tests/test_spec_drift.py`)

`extract_changed_paths` (real temp git repo; deterministic identity via
`-c user.email=… -c user.name=…`; `GIT_*_DATE` not needed since we never assert hashes):
- baseline commit → clean tree → `()`.
- modify a tracked file → it surfaces.
- add an untracked file → it surfaces.
- delete a tracked file → it surfaces.
- a path with a space → survives `-z` parsing.
- non-git temp dir → `()`.

`check_spec_drift` (build a ScanContext over a temp repo, or stub `ctx.changed_paths`):
- coupling with `when_changed` in diff + a `requires` absent → 1 finding (assert
  when/req in evidence/meta).
- `when_changed` + all `requires` present → 0.
- `when_changed` not in diff → 0 (dormant).
- glob `when_changed`/`requires` match.
- no `drift_couplings` key → 0.
- two runs on identical dirty state are equal (determinism).

## 9. Dogfood-safety proof

Impl commit changes: `src/codas/adapters/git.py` (new), `src/codas/facts/context.py`,
`src/codas/policies/spec_drift.py` (new), `src/codas/app/check.py`,
`tests/test_spec_drift.py` (new), `tests/test_codas_check.py`. No `drift_couplings` are
authored in the live `claims.yml`, so `check_spec_drift` returns `[]` regardless of the
dirty diff → `codas check .` shows 0 spec-drift findings pre- and post-commit. The
later `program.yml` task-link commit is likewise unaffected (no coupling targets it).

## 10. Non-goals / limitations (v0)

- No autonomous `must_update_if_changed` gate (materiality is semantic → host-agent
  judged → vouched coupling). Advisory surfacing deferred.
- File-level grounding only; hunk-level "how" is the host agent's to read.
- A vouched coupling is still all-or-nothing per file (no sub-file precision); the call
  graph (`ctx.calls()`) is the future path to symbol-level couplings.

## 11. Review note

The direction BLOCKER from the first codex round is resolved by this rewrite (correct
schema direction + materiality-as-claim). Codex's technical SHOULDs are folded: `-z`
NUL diff parsing (§3), non-git/no-HEAD → `()` (§3), root-prefix concern is moot (v0 keys
off couplings, not unit prefixes), changed_paths-excluded-from-inventory confirmed (§4).
Given the pivot is grounded in the authoritative schema + explicit user direction, the
next codex pass runs on the IMPLEMENTATION (rhythm step 6) rather than a second design
round.
