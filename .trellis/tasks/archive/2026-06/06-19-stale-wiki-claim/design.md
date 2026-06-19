# Design — P5 D2: stale-wiki-claim policy

Authority: plan §2 (verify evidence + authority), §2.1 (wiki not a fact source by
itself), §5 (Wiki output = stale wiki findings), `codas-product.md` Duplicate Risks
(wiki must not out-rank constraint sources). Consumes the D1 `wiki_claims` facts via
the ScanContext seam; reuses the `document_set` policy's glob-aware matcher.

## Verification model

Per the §2 chain (claim → verified governance fact), each wiki claim is verified
against the repo fact appropriate to its `kind`. D2 owns exactly the dimensions no
existing policy covers:

| kind             | D2 check                                              | why not elsewhere                          |
|------------------|-------------------------------------------------------|--------------------------------------------|
| `canonical_source` (literal) | authority: matched by config authoritative∪supporting? | authority is new; no policy checks it      |
| `canonical_source`/`evidence`/`sync_target` | existence: `exists` is True?      | code spans; `stale_claim` checks links only |
| `concept_page` (link) | — (none)                                          | `stale_claim` already flags broken links   |
| glob `canonical_source` | existence only (authority-exempt)               | a tree pointer, not a per-artifact authority |

Why `stale_claim` does not already cover this: `stale_claim` filters
`claim.kind == "link"` (`policies/stale_claim.py:30`), so wiki code-span paths
(`canonical_source`/`evidence`/`sync_target`) are invisible to it. D2 is strictly
additive (code-span existence + authority); `concept_page` link existence stays with
`stale_claim` (no double-finding).

## Policy: `src/codas/policies/stale_wiki_claim.py`

```python
from __future__ import annotations

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext
from codas.policies.document_set import _matches_any  # intra-codas-policies reuse

_EXISTENCE_KINDS = ("canonical_source", "evidence", "sync_target")


def check_stale_wiki_claim(ctx: ScanContext) -> list[Finding]:
    """Verify Atlas Wiki claims against repo facts (stale_wiki_claim).

    Plan §2: a wiki claim becomes a governance fact only when Codas can verify its
    evidence AND authority. D2 owns the dimensions no other policy covers:

    - authority: a literal `canonical_source` must be a constraint source declared
      authoritative/supporting in config (glob-aware) — the wiki must not out-rank
      the constraint sources (codas-product.md Duplicate Risks). Glob canonical
      sources are tree pointers, not per-artifact authority -> existence-only.
    - existence: `canonical_source`/`evidence`/`sync_target` are code-span paths
      that `stale_claim` (links only) never checks; a missing one is stale.

    `concept_page` link existence is left to `stale_claim`. Consumes facts via the
    ScanContext seam (no adapter import). Deterministic (total-key sort).
    """
    claims = ctx.wiki_claims().claims
    declared = set(ctx.config.authoritative_sources) | set(ctx.config.supporting_sources)
    findings: list[Finding] = []

    for claim in claims:
        # authority (literal canonical sources only)
        if (
            claim.kind == "canonical_source"
            and claim.path_kind == "literal"
            and not _matches_any(claim.path, declared)
        ):
            findings.append(
                Finding(
                    severity="warning",
                    check_id="stale-wiki-claim",
                    message=(
                        "Wiki cites a canonical source that config does not declare "
                        f"authoritative or supporting: {claim.path}"
                    ),
                    evidence=[Evidence(path=claim.source, line=claim.line, detail=claim.path)],
                    recommendation=(
                        "Declare the path in .codas/config.yml constraint_sources, or "
                        "remove the wiki canonical-source claim."
                    ),
                )
            )
        # existence (code-span kinds)
        if claim.kind in _EXISTENCE_KINDS and not claim.exists:
            findings.append(
                Finding(
                    severity="warning",
                    check_id="stale-wiki-claim",
                    message=f"Wiki {claim.kind} claim references a missing path: {claim.path}",
                    evidence=[Evidence(path=claim.source, line=claim.line, detail=claim.path)],
                    recommendation="Restore the path or update the wiki claim.",
                )
            )

    findings.sort(
        key=lambda f: (
            f.evidence[0].path,
            f.evidence[0].line or 0,
            f.evidence[0].detail or "",
            f.message,
        )
    )
    return findings
```

Notes:
- A single claim can in principle yield **two** findings (a literal canonical_source
  that is both unauthorized AND missing). That is correct — two distinct defects —
  and the `f.message` tiebreak keeps the sort total. Not deduped.
- `_matches_any(path, patterns)` uses `fnmatch.fnmatch`, whose `*` spans `/`, so the
  config glob `.trellis/spec/**/*.md` matches the literal
  `.trellis/spec/codas/workflow/task-system.md` (verified empirically) — that is why
  the authority check is 0-on-repo.
- `ctx.config.authoritative_sources` / `supporting_sources` already exist (used by
  `app/preflight.py`). No new config plumbing.

## Wiring: `app/check.py`

Add the import and one call after `check_dependency_direction(ctx)`:

```python
from codas.policies.stale_wiki_claim import check_stale_wiki_claim
...
findings.extend(check_stale_wiki_claim(ctx))
```

## Declaration: `.codas/policies.yml`

```yaml
  stale_wiki_claim:
    severity: warning
```

(Add a description consistent with the other policy entries.)

## Dogfooding / determinism

- **0-on-repo** (verified by probe before design): all 11 literal `canonical_source`
  paths are matched by a config authoritative/supporting pattern (10 exact + the
  spec page via the `.trellis/spec/**/*.md` glob); `.trellis/tasks/**` is glob →
  authority-exempt; all 47 wiki code-span/glob paths exist. → no finding.
- New public symbol `check_stale_wiki_claim` unique under `src/`; no new private
  helper (reuses `_matches_any`) → no `duplicate_implementation` risk.
- Boundary: the policy imports `codas.facts.context` (seam types) + a sibling policy
  helper — NO adapter import, so `dependency_direction` stays green.
- **Orchestration-test trap**: `tests/test_codas_check.py` monkeypatches every
  ctx-consuming policy in its build-once-and-forward test. Adding a 5th ctx consumer
  (`check_stale_wiki_claim`) means it MUST be added to that patch set, or the test
  feeds a `MagicMock` ctx into the real policy and breaks (hit twice in P3). Update
  that test in this slice.
- No new structure unit / governance file (new file under the owned
  `src/codas/policies` dir; policies.yml edit is an existing governed file).

## Tests (`tests/test_stale_wiki_claim.py`)

Build temp repos with a `.codas/config.yml` (authoritative + supporting + a glob
pattern), a `.codas/wiki/`, and target files; call `check_stale_wiki_claim` on a
`build_scan_context(repo, load_codas_config(...))`.

- **authority pass (literal + glob-matched)**: canonical sources that are declared
  (exact) or matched by a config glob → no finding.
- **authority fail**: a canonical source not in config authority → exactly one
  warning naming the path.
- **glob canonical source exempt**: a wiki `canonical_source` glob not in config →
  no authority finding (existence-only).
- **existence fail**: a missing `evidence` and a missing `sync_target` path → one
  warning each; a missing `canonical_source` → existence warning too.
- **concept_page not double-flagged**: a broken `concept_page` link produces NO
  `stale-wiki-claim` finding (test comment: `stale_claim` owns it).
- **determinism**: two calls return equal finding lists.
- **repo regression** (subprocess or in-process): `check_stale_wiki_claim` on this
  repo returns `[]`; `codas check .` exits 0.

## Open questions for codex design review

1. **Authority for globs** — exempting glob `canonical_source` from the authority
   check (existence-only) vs attempting glob-subset reasoning against config globs.
   Exempt is simple + 0-on-repo; is it too lenient (a wiki could assert
   `secret/**` as canonical unchecked)? Existence still covers it.
2. **Severity** — warning (consistent with `stale_claim`, wiki is `supporting`) vs
   error for the authority over-claim specifically (§2 framing is strong). Leaning
   warning to match the surface's authority tier and keep one severity for the
   policy.
3. **Existence overlap precision** — confirm `stale_claim` really ignores code spans
   (it filters `kind == "link"`), so D2's code-span existence is non-redundant, and
   that `concept_page` (link) is the only kind to defer. Any wiki code-span that is
   ALSO emitted as a `doc_claim` link? (No: D1 emits `concept_page` from links,
   the others from code spans.)
4. **`sync_target` reverse-pointer** — deferring the structure-map
   `must_update_if_changed` consistency check (wiki says update X; does structure
   agree?) and verifying only existence in D2 — right scope, or is the reverse
   pointer the real point of `sync_target` and should ship now?
5. **Two findings per claim** — allowing a literal canonical_source to emit both an
   authority and an existence finding, vs collapsing to one per claim. Leaning keep
   (distinct defects).
