from __future__ import annotations

from pathlib import Path

from codas.config.loader import ConfigLoadError, load_codas_config, load_policies, load_waivers
from codas.core.models import CheckReport, Evidence, Finding
from codas.policies.config_sources import check_config_sources
from codas.policies.dogfooding import check_dogfooding_protocol
from codas.policies.program_plan import check_program_plan
from codas.policies.structure_map import check_structure_map
from codas.policies.trellis_context import check_trellis_context
from codas.policies.waivers import check_waivers


def run_check(repo: Path) -> CheckReport:
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
        return CheckReport(repo=repo.as_posix(), findings=findings)

    findings.extend(check_config_sources(repo, config))
    findings.extend(check_dogfooding_protocol(repo, config))
    findings.extend(check_trellis_context(repo, config))
    findings.extend(check_structure_map(repo, config))
    findings.extend(check_program_plan(repo, config))

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

    return CheckReport(repo=repo.as_posix(), findings=findings)


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
