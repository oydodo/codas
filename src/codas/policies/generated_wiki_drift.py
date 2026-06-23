from __future__ import annotations

from pathlib import Path

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext
from codas.structure.loader import StructureMapError, load_structure_map
from codas.structure.program_loader import ProgramPlanError, load_program_plan

STRUCTURE_SOURCE = ".codas/structure.yml"
PROGRAM_SOURCE = ".codas/program.yml"


def check_generated_wiki_drift(ctx: ScanContext) -> list[Finding]:
    """Verify the atlas:claims of committed generated wiki pages against facts.

    The "VERIFY" half of the wiki spine (plan §17: the wiki follows the facts, never
    leads them). A generated page under ``.codas/wiki/generated/`` carries machine-
    checkable claims; this policy is the deterministic guardrail that keeps the LLM
    generation path honest — a claim the facts contradict is a verifiable lie and an
    error, so a host agent cannot smuggle an unverified assertion into a generated page.

    Two checks:

    - **structural** (architecture doc §3 link ③): a generated page must carry a
      nonempty ``atlas:claims`` block with at least one claim — else error (an ungrounded
      generated page).
    - **fact-consistency** (link ④): each ``unit: <id> -> <path>`` must match a Structure
      Map unit, each ``roadmap: <id> -> <status>`` must match a Program Plan work item.
      A mismatch or unknown subject is an error.

    Freshness is NOT checked here: the always-on gate cannot re-render to byte-compare
    without a second full inventory scan (ScanContext exposes facts, not a built
    inventory), so freshness is the opt-in ``codas wiki --verify`` (D3c) / CI byte-compare
    (``verify_generated_sections``: re-render + byte-compare; the page carries no embedded
    hash). The claim checks above catch the *meaningful* staleness (a unit/roadmap that no
    longer matches the facts) as an error, which forces a regenerate when facts move.

    Consumes facts via the ScanContext seam (no adapter import, §11). Severity error.
    Deterministic (total-key sort). On loader failure the corresponding claim kind is
    skipped (not flagged) — a broken structure map / program plan is already its own
    load-error finding; flagging every claim "unknown" would be a noisy cascade.
    """
    pages = ctx.generated_claims().pages
    if not pages:
        return []

    units = _unit_paths(ctx.repo)  # {id: path} or None on load failure
    statuses = _work_item_status(ctx.repo)  # {id: status} or None on load failure
    findings: list[Finding] = []

    for page in pages:
        if not (page.has_block and page.claims):
            findings.append(
                Finding(
                    severity="error",
                    check_id="generated-wiki-drift",
                    message=(
                        "Generated page must embed a nonempty atlas:claims block with at "
                        "least one claim"
                    ),
                    evidence=[Evidence(path=page.source)],
                    recommendation="Regenerate the page with `codas wiki --write`.",
                    meta={"page": page.source},
                )
            )
            continue

        for claim in page.claims:
            if claim.kind == "unit" and units is not None:
                finding = _verify_mapping(
                    claim, units, "structure unit", STRUCTURE_SOURCE, "path"
                )
                if finding is not None:
                    findings.append(finding)
            elif claim.kind == "roadmap" and statuses is not None:
                finding = _verify_mapping(
                    claim, statuses, "work item", PROGRAM_SOURCE, "status"
                )
                if finding is not None:
                    findings.append(finding)

    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.message,
        )
    )
    return findings


def _verify_mapping(claim, facts, noun, fact_source, field) -> Finding | None:
    """Flag a generated claim whose subject is unknown or whose value mismatches facts."""
    if claim.subject not in facts:
        message = f"Generated page claims unknown {noun} '{claim.subject}'"
    elif facts[claim.subject] != claim.value:
        message = (
            f"Generated page claims {noun} '{claim.subject}' {field} '{claim.value}' "
            f"but {fact_source} says '{facts[claim.subject]}'"
        )
    else:
        return None
    return Finding(
        severity="error",
        check_id="generated-wiki-drift",
        message=message,
        evidence=[Evidence(path=claim.source, line=claim.line, detail=claim.subject)],
        recommendation="Regenerate the page with `codas wiki --write`.",
        meta={"subject": claim.subject, "kind": claim.kind},
    )


def _unit_paths(repo: Path) -> dict[str, str] | None:
    path = repo / ".codas" / "structure.yml"
    if not path.exists():
        return None
    try:
        structure_map = load_structure_map(path, source=STRUCTURE_SOURCE)
    except StructureMapError:
        return None  # structure_map_loads owns the load-error finding
    return {unit.id: unit.path for unit in structure_map.units}


def _work_item_status(repo: Path) -> dict[str, str] | None:
    path = repo / ".codas" / "program.yml"
    if not path.exists():
        return None
    try:
        program = load_program_plan(path, source=PROGRAM_SOURCE)
    except ProgramPlanError:
        return None  # program_plan_loads owns the load-error finding
    return {item.id: item.status for item in program.work_items}
