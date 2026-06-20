from __future__ import annotations

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext


def check_stale_html_claim(ctx: ScanContext) -> list[Finding]:
    """Flag path references in authoritative/supporting ``.html`` whose target is missing.

    The HTML analogue of ``stale_claim`` (plan §10 "doc path references point to existing
    files"), closing the gap that authoritative ``.html`` produces no facts: the markdown
    adapter scans ``.md`` only, so a path named in an HTML spec drifts unseen. Verifies
    Layer 1 — path/link EXISTENCE — over the config-scoped ``html_claims`` fact stream.

    Unlike ``stale_claim`` (which checks ``kind=="link"`` only because a markdown backtick
    span is routinely an illustrative prose mention), BOTH kinds are checked here: the
    ``html_claims`` keep-filter already restricts to real path shapes (slash + known ext +
    path-shape gate, and `<pre>` example blocks are excluded), so a kept HTML reference is
    a genuine path claim. Disjoint fact stream from ``stale_claim`` (markdown
    ``doc_claims``) -> the two never double-report. Code-identifier mention staleness (a
    bare ``<code>policy_name</code>``) is Layer 2, deliberately out of scope.

    Consumes normalized facts via the ``ScanContext`` (plan §11) — it does not import the
    HTML adapter itself. Warning severity, consistent with ``stale_claim``/
    ``stale_wiki_claim``. Whole working tree, no diff, deterministic.
    """
    claims = ctx.html_claims()

    findings = [
        Finding(
            severity="warning",
            check_id="stale-html-claim",
            message=f"HTML doc references a missing path: {claim.path}",
            evidence=[Evidence(path=claim.source, line=claim.line, detail=claim.path)],
            recommendation="Update the reference or restore the target path.",
        )
        for claim in claims
        if not claim.exists
    ]
    # html_claims is already sorted by (source, line, path, fragment, kind); re-sort on a
    # total key (detail = target path) so two broken refs on the same source+line never
    # tie-break on list-insertion order.
    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.evidence[0].detail or "",
        )
    )
    return findings
