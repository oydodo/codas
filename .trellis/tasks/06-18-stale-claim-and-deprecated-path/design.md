# Design: Stale claim and deprecated path policies

## Principle: facts stay neutral, policies decide findings

The doc-claim index (`extract_doc_claims`) and Structure Map loader already
produce complete, neutral facts. These policies are pure consumers — no changes
to the adapters or loaders. Scope decisions (link-only, literal-prefix) live in
the policy layer, never in the fact layer, so the inventory JSON is unchanged.

## Policy 1: `stale_claim` (`src/codas/policies/stale_claim.py`)

Signature: `check_stale_claim(repo: Path, config: CodasConfig) -> list[Finding]`

Algorithm:
1. Resolve workspace roots from `config.raw` (reuse the same `(".",)` default the
   inventory uses; factor a shared `workspace_roots(raw)` helper so policy and
   inventory cannot drift).
2. `files = discover_files(repo, roots)`.
3. `claims = extract_doc_claims(repo, tuple(files))`.
4. For each `claim` where `claim.kind == "link"` and `not claim.exists`, emit:
   ```
   Finding(
       severity="warning",
       check_id="stale-claim",
       message=f"Markdown link points to a missing path: {claim.path}",
       evidence=[Evidence(path=claim.source, line=claim.line, detail=claim.path)],
       recommendation="Update the link or restore the target path.",
   )
   ```
5. Findings already arrive sorted because `extract_doc_claims` sorts by
   `(source, line, path, fragment, kind)`; preserve that order (no re-sort needed,
   but a defensive stable sort by `(source, line, path)` is cheap and explicit).

Why link-only: a `[text](path)` link is a navigational commitment — a renderer
produces a broken link. A backtick code span is a prose mention with no
navigational guarantee, and is frequently illustrative. Restricting the first cut
to links matches §10 "Markdown path references" (a reference = a link) and keeps
false positives at zero. Code spans + fragment anchors are the §10 Later Expansion.

Severity = warning, matching `.codas/policies.yml` `stale_claim.severity`.

## Policy 2: `deprecated_path_used` (`src/codas/policies/deprecated_path.py`)

Signature: `check_deprecated_path_used(repo: Path, config: CodasConfig) -> list[Finding]`

Algorithm:
1. If `.codas/structure.yml` is absent, return `[]` (the missing file is already
   reported by `config_sources`; mirror `check_structure_map`'s guard).
2. `structure_map = load_structure_map(path, source=STRUCTURE_SOURCE)`. On
   `StructureMapError`, return `[]` — malformedness is `structure_map_loads`'
   responsibility, not this policy's (avoid double-reporting).
3. Resolve roots, `files = discover_files(repo, roots)`.
4. For each `dep` in `structure_map.deprecated_paths`:
   - `prefix = normalize_path(dep.path)` (reuse `index.normalize_path`).
   - Skip empty prefix (an empty/`.` deprecated path would match the whole repo —
     treat as misconfiguration, not a per-file finding; defensive guard).
   - For each `path` in `files` where `path == prefix or path.startswith(prefix + "/")`,
     emit an error Finding.
5. Finding:
   ```
   Finding(
       severity="error",
       check_id="deprecated-path-used",
       message=f"Artifact lives under a {dep.status or 'deprecated'} path: {path}",
       evidence=[
           Evidence(path=path, detail=dep.path),
           Evidence(path=STRUCTURE_SOURCE, detail=f"deprecated_paths[{dep.id}]"),
       ],
       recommendation=(
           f"Move it under {dep.replacement}." if dep.replacement
           else "Move it out of the deprecated path."
       )
       + (f" ({dep.reason})" if dep.reason else ""),
       meta={"deprecated_path": dep.path, "status": dep.status,
             "replacement": dep.replacement},
   )
   ```
   (Codex review #8) The second Evidence points the reviewer at the rule source
   in `.codas/structure.yml`. No line number: the structure loader does not yet
   track per-field source lines; adding line tracking is a follow-up, not part of
   this two-policy slice. The artifact-path Evidence is the actionable one.
6. Sort findings by `(path, dep.path)` for determinism (iteration over
   `deprecated_paths` + sorted `files` is already deterministic, but sort
   explicitly so output never depends on YAML key order).

Severity = error, matching `.codas/policies.yml` and §8 ("Error with replacement
path when known").

Match semantics mirror `index._matches` (prefix or `prefix/...`), so a file named
`scripts/harness-guardian` does NOT match deprecated `scripts/harness-guard`.
Literal prefixes only; glob deprecated paths are a non-goal.

**Whole-tree vs §8 "new files" (Codex review #3).** §8 phrases the rule as "New
files must not be added under deprecated or removed paths." This slice flags ANY
existing tracked file under a deprecated prefix — a deliberate, stricter superset.
Rationale: diff scoping is a documented later expansion (PRD non-goal); a whole-
tree invariant cannot produce a false positive the diff-aware version wouldn't
also eventually catch (if no file may be *added* under a removed path, none may
*exist* there). Both `status` values fire — `removed` and `deprecated` alike (§8
names both); `status` is descriptive only, never a firing gate.

**Status validation (Codex review #4) — follow-up, not this slice.** The loader
accepts any `deprecated_paths[].status` string (`DeprecatedPath.status` defaults
to `""`). The policy renders it defensively (`dep.status or "deprecated"`), so a
typo cannot crash or misfire — it only affects message text. Validating status to
`{deprecated, removed}` belongs in the structure loader (`structure_map_loads`),
with its own test and a possible schema-claim note; it is out of scope for these
two policies and tracked as a follow-up.

## Wiring (`src/codas/app/check.py`)

Add both after `check_structure_map` in `run_check`:
```
findings.extend(check_stale_claim(repo, config))
findings.extend(check_deprecated_path_used(repo, config))
```
Order: structure → deprecated_path_used (structure-derived) → ... stale_claim can
sit near the document/markdown checks. Final report ordering is by insertion; the
reporting layer already groups by severity, so exact insertion order is cosmetic.

## Shared helper

`_workspace_roots` currently lives in `structure/inventory.py`. Extract it to a
shared location both inventory and the new policies import, to prevent the
"default roots" rule from forking. Candidate: `structure/index.py` (already the
home of `discover_files` / `normalize_path`) as `workspace_roots(raw)`. Update
`inventory.py` to import it. This is a pure refactor, behavior-preserving.

## Determinism

- No timestamps, no randomness.
- `discover_files` returns a sorted list; `extract_doc_claims` returns a sorted
  list; both policies sort their findings by stable keys.
- `codas inventory` is untouched → byte-identical across runs (verify with a
  2x diff in the bootstrap check).

## Tests (`tests/test_stale_claim_policy.py`, `tests/test_deprecated_path_policy.py`)

Use a temp-repo fixture pattern (mirror existing policy tests). Each builds a
minimal `.codas/config.yml` + `.codas/structure.yml` and a few files.

`stale_claim`:
- broken link `[x](missing.md)` → one warning finding (path, line, source in evidence).
- existing link `[x](real.md)` → no finding.
- code span `` `missing.md` `` → no finding (deferred).
- external link `[x](https://...)` and image `![x](missing.png)` → no finding.
- determinism: two files with broken links → findings sorted by (source, line).

`deprecated_path_used`:
- file under deprecated prefix → error finding with replacement in recommendation.
- file whose name shares the prefix but is a sibling (`scripts/harness-guardian`)
  → no finding (prefix-boundary correctness).
- deprecated path with no replacement → generic recommendation, no crash.
- missing/empty structure.yml → no finding (guard).

Plus a real-repo assertion in `test_codas_check.py` (Codex review #6): assert the
specific check_ids `"stale-claim"` and `"deprecated-path-used"` are ABSENT from
`codas check .` output — not merely "no error findings," since `stale_claim` is a
warning and a warning-only regression must still fail the dogfood test. Keep/raise
the existing clean-repo assertion to `report.findings == []` if it is currently
weaker.

## Follow-ups (deferred from Codex impl review, out of two-policy scope)

- **Shared scan context** (impl #4): both policies call `discover_files`
  independently of each other and of the inventory. Correctness risk is only a
  mid-run tree mutation; defensively low. The clean fix is a single tree scan
  passed to every policy (a scan/inventory context in `run_check`), which changes
  the shared `check_x(repo, config)` contract — a P2 infrastructure task, not a
  per-policy change. Tracked, not done here.
- **Structure loader `deprecated_paths` validation** (design #4 + impl #3): the
  loader accepts any `status` string and any `path`, including one that normalizes
  to the repo root (`.`). The policy guards against root-prefix (skips it) and
  renders status defensively, so behavior is correct today, but malformed
  governance data is silent. Fold status-enum + root-path rejection into a single
  `structure_map_loads` hardening follow-up (own test, possible schema-claim note).

## Dogfooding checklist

- Concepts touched: `stale_claim`, `deprecated_path_used` (declared in
  `.codas/policies.yml`). Claim-source edit (Codex review #2): the current
  `stale_claim` description promises "paths, commands or concepts" — wider than the
  link-only First Implementation. Narrow it to state the implemented scope, e.g.
  "Markdown link references must point to existing paths (code-span and anchor
  checks are later expansion)," so the declared claim matches behavior and
  `spec_drift` stays honest. `deprecated_path_used` description already matches.
- New artifacts: two policy modules under `codas-policies`, two test modules under
  `codas-tests` — both governed by existing Structure Units, so `inventory.unowned`
  stays empty.
- No new module directory → no `.codas/structure.yml` unit edit.
- Behavior is new but matches existing policy descriptions and §10/§8 First
  Implementation rules → no implementation-plan / schema claim change required.
- Bootstrap gate: `unittest discover` + `git status --short` clean.
