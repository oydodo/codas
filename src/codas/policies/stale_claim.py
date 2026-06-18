from __future__ import annotations

from pathlib import Path

from codas.adapters.markdown import extract_doc_claims
from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding
from codas.structure.index import discover_files, workspace_roots


def check_stale_claim(repo: Path, config: CodasConfig) -> list[Finding]:
    """Flag Markdown link references whose target path no longer exists (stale_claim).

    First Implementation (plan §10): "Markdown path references point to existing
    files." Scoped to links (``[text](path)``) only — a link is a navigational
    commitment, whereas a backtick code span is a prose mention that is routinely
    illustrative and produces false positives. Code-span path mentions and fragment
    anchors are the §10 Later Expansion. Whole working tree, no diff, deterministic.
    """
    roots = workspace_roots(config.raw)
    files = discover_files(repo, roots)
    claims = extract_doc_claims(repo, tuple(files))

    findings = [
        Finding(
            severity="warning",
            check_id="stale-claim",
            message=f"Markdown link points to a missing path: {claim.path}",
            evidence=[Evidence(path=claim.source, line=claim.line, detail=claim.path)],
            recommendation="Update the link or restore the target path.",
        )
        for claim in claims
        if claim.kind == "link" and not claim.exists
    ]
    # extract_doc_claims already sorts by (source, line, path, fragment, kind);
    # re-sort on a total key (detail = target path) so two broken links on the
    # same source+line never tie-break on list-insertion order.
    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.evidence[0].detail or "",
        )
    )
    return findings
