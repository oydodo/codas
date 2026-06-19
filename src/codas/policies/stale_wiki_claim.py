from __future__ import annotations

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext

# Reused intra-`codas-policies` (same unit, no adapter import -> dependency_direction
# stays green). `_matches_any` is the glob-aware (fnmatch) constraint-source matcher
# that document_set already uses to cross-check authority; keeping a single
# definition avoids a duplicate_implementation flag. If document_set is refactored,
# move this helper to a shared codas/policies utility rather than re-defining it.
from codas.policies.document_set import _matches_any

# Code-span claim kinds whose target path `stale_claim` never checks (it filters
# `kind == "link"`), so their existence is D2's to verify. `concept_page` (a link)
# is deliberately excluded -> `stale_claim` owns broken-link findings.
_EXISTENCE_KINDS = ("canonical_source", "evidence", "sync_target")


def check_stale_wiki_claim(ctx: ScanContext) -> list[Finding]:
    """Verify Atlas Wiki claims against repo facts (stale_wiki_claim).

    Plan §2: "A wiki claim becomes a governance fact only when Codas can verify its
    evidence and authority." D2 owns the two dimensions no existing policy covers:

    - **authority** (literal `canonical_source`): a wiki "Canonical Source" must be a
      constraint source the repo actually declares — `authoritative` or `supporting`
      in `.codas/config.yml` (glob-aware via `_matches_any`). A wiki page elevating a
      path to canonical that config does not treat as a constraint source is the §2
      over-claim ("wiki must not out-rank the constraint sources"). Glob canonical
      sources (e.g. `.trellis/tasks/**`) are navigational tree pointers, not
      per-artifact authority -> existence-verified only, authority-exempt.
    - **existence** (`canonical_source`/`evidence`/`sync_target`): these are
      code-span paths that `stale_claim` (links only) never checks; a missing one is
      a stale wiki claim.

    Consumes facts via the ScanContext seam (no adapter import, plan §11).
    Deterministic (total-key sort). Severity warning — the wiki is a `supporting`
    authority surface, so drift is a warning, not a hard gate.
    """
    claims = ctx.wiki_claims().claims
    declared = set(ctx.config.authoritative_sources) | set(ctx.config.supporting_sources)
    findings: list[Finding] = []

    for claim in claims:
        # Authority is checked on literal canonical sources only. `path_kind` is
        # "glob" iff the path contains "*" (wiki adapter); "*" is reserved glob
        # syntax for canonical-source values, so a literal filename containing "*"
        # would be treated as a glob and skip authority (existence still applies).
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
                    evidence=[
                        Evidence(path=claim.source, line=claim.line, detail=claim.path)
                    ],
                    recommendation=(
                        "Declare the path in .codas/config.yml constraint_sources, or "
                        "remove the wiki canonical-source claim."
                    ),
                )
            )
        if claim.kind in _EXISTENCE_KINDS and not claim.exists:
            findings.append(
                Finding(
                    severity="warning",
                    check_id="stale-wiki-claim",
                    message=(
                        f"Wiki {claim.kind} claim references a missing path: {claim.path}"
                    ),
                    evidence=[
                        Evidence(path=claim.source, line=claim.line, detail=claim.path)
                    ],
                    recommendation="Restore the path or update the wiki claim.",
                )
            )

    # extract_wiki_claims already sorts by (source, line, kind, path); re-sort on a
    # total key (message included) so an authority + existence finding on the same
    # claim never tie-break on list-insertion order.
    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.evidence[0].detail or "",
            finding.message,
        )
    )
    return findings
