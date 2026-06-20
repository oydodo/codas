from __future__ import annotations

from pathlib import Path

from codas.config.loader import ConfigLoadError, load_codas_config, load_policies, load_waivers
from codas.core.models import CheckReport, Evidence, Finding
from codas.facts.context import ScanContext, build_scan_context
from codas.policies.config_sources import check_config_sources
from codas.policies.dependency_direction import check_dependency_direction
from codas.policies.deprecated_path import check_deprecated_path_used
from codas.policies.duplicate_implementation import check_duplicate_implementation
from codas.policies.duplicate_symbol import check_duplicate_symbol
from codas.policies.document_set import check_document_set
from codas.policies.dogfooding import check_dogfooding_protocol
from codas.policies.fact_coupling import check_fact_coupling
from codas.policies.generated_wiki_drift import check_generated_wiki_drift
from codas.policies.missing_owner import check_missing_structure_owner
from codas.policies.policy_registry import check_policy_registry
from codas.policies.program_plan import check_program_plan
from codas.policies.stale_claim import check_stale_claim
from codas.policies.stale_html_claim import check_stale_html_claim
from codas.policies.stale_wiki_claim import check_stale_wiki_claim
from codas.policies.structure_drift import check_structure_drift
from codas.policies.structure_map import check_structure_map
from codas.policies.trellis_context import check_trellis_context
from codas.policies.waivers import check_waivers


def run_check(repo: Path) -> CheckReport:
    """Run all policies and return the report (the public check entry point)."""
    report, _ = run_check_with_context(repo)
    return report


def run_check_with_context(repo: Path) -> tuple[CheckReport, ScanContext | None]:
    """Run all policies, returning the report and the run's ``ScanContext``.

    The ctx is exposed so ``check --json`` can reuse the single scan its policies ran
    for the provenance inventory instead of triggering a second full scan/parse. It
    is ``None`` only when config failed to load (an early return before any scan).
    """
    findings: list[Finding] = []
    config_path = repo / ".codas" / "config.yml"

    try:
        config = load_codas_config(config_path)
    except ConfigLoadError as error:
        findings.append(
            Finding(
                severity="error",
                check_id="config-load-error",
                message=str(error),
                evidence=[Evidence(path=_rel(repo, config_path))],
            )
        )
        return CheckReport(repo=repo.as_posix(), findings=findings), None

    ctx = build_scan_context(repo, config)

    findings.extend(check_config_sources(repo, config))
    findings.extend(check_dogfooding_protocol(repo, config))
    findings.extend(check_trellis_context(repo, config))
    findings.extend(check_structure_map(repo, config))
    findings.extend(check_missing_structure_owner(repo, config))
    findings.extend(check_structure_drift(repo, config))
    findings.extend(check_deprecated_path_used(repo, config))
    findings.extend(check_program_plan(repo, config))
    findings.extend(check_document_set(repo, config))
    findings.extend(check_stale_claim(ctx))
    findings.extend(check_stale_html_claim(ctx))
    findings.extend(check_duplicate_symbol(ctx))
    findings.extend(check_duplicate_implementation(ctx))
    findings.extend(check_dependency_direction(ctx))
    findings.extend(check_stale_wiki_claim(ctx))
    findings.extend(check_fact_coupling(ctx))
    findings.extend(check_generated_wiki_drift(ctx))
    findings.extend(check_policy_registry(ctx))

    policies_path = repo / ".codas" / "policies.yml"
    try:
        load_policies(policies_path)
    except ConfigLoadError as error:
        findings.append(
            Finding(
                severity="error",
                check_id="policy-load-error",
                message=str(error),
                evidence=[Evidence(path=_rel(repo, policies_path))],
            )
        )

    waivers_path = repo / ".codas" / "waivers.yml"
    try:
        waivers = load_waivers(waivers_path)
    except ConfigLoadError as error:
        findings.append(
            Finding(
                severity="error",
                check_id="waiver-load-error",
                message=str(error),
                evidence=[Evidence(path=_rel(repo, waivers_path))],
            )
        )
    else:
        findings.extend(check_waivers(repo, waivers_path, waivers))

    return CheckReport(repo=repo.as_posix(), findings=findings), ctx


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
