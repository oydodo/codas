from __future__ import annotations

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext


def check_code_anchor(ctx: ScanContext) -> list[Finding]:
    """Verify the code anchors of hand-authored Atlas code-wiki pages resolve (code_anchor).

    The deterministic half of the code-wiki: a code-wiki page (`.codas/wiki/code/**`) is
    advisory PROSE — Codas does NOT verify its meaning — plus a structured `anchor_symbol`
    claim block asserting "this page describes the symbol NAME defined in PATH". This policy
    checks ONLY those anchors: does a symbol fact (module == path, name == name) exist?

    It catches the CODE -> DOC drift the user named: an agent renames/moves a symbol during
    implementation and forgets the wiki — the anchor stops resolving and this surfaces it.
    The doc -> code direction is left to the Trellis workflow (user-driven doc edits the
    agent follows) and is not gated here.

    ALL-OPEN severity = WARNING, never an error: the `symbols` family is OPEN-world (a
    non-resolving anchor may mean the code genuinely moved OR that it now takes a
    conditional/dynamic form the static extractor misses — codas.facts.openworld). Per the
    open-world invariant a policy MUST NOT hard-gate on the absence of an open-world fact, so
    a missing anchor is a warning carrying that caveat, not a blocking error. (A
    closed-world hard-gate on a genuinely-deleted top-level def is a later optimization.)

    §11: consumes facts via the ScanContext only (the code-anchor claims + symbols), imports
    no adapter. The code-wiki prose never enters the inventory hash (its claims are
    position-stripped policy-time facts), so this policy does not perturb determinism.
    """
    anchors = ctx.code_anchor_claims().claims
    if not anchors:
        return []

    defined = {(d.module, d.name) for d in ctx.symbols().definitions}

    findings = [
        Finding(
            severity="warning",
            check_id="code-anchor",
            message=(
                f"code-wiki anchor does not resolve: {anchor.path}:{anchor.name} "
                f"(concept '{anchor.concept}'). The symbol is not in the current symbol "
                "facts — the code may have moved (update the wiki page), OR it now takes a "
                "dynamic/conditional form the open-world extractor misses (a lower bound; "
                "verify by hand)."
            ),
            evidence=[Evidence(path=anchor.source, line=anchor.line, detail=f"{anchor.path}:{anchor.name}")],
            recommendation="Update the code-wiki page's anchor_symbol claim, or restore the symbol.",
        )
        for anchor in anchors
        if (anchor.path, anchor.name) not in defined
    ]
    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.evidence[0].detail or "",
        )
    )
    return findings
