from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from codas.config.loader import load_codas_config, load_policies, load_waivers
from codas.structure.document_loader import load_document_manifest
from codas.structure.loader import load_structure_map
from codas.structure.program_loader import load_program_plan

_CONFIG = ".codas/config.yml"
_POLICIES = ".codas/policies.yml"
_WAIVERS = ".codas/waivers.yml"
_STRUCTURE = ".codas/structure.yml"
_PROGRAM = ".codas/program.yml"
_DOCUMENTS = ".codas/documents.yml"
# Prototype paths removed in P0; a leftover means an incomplete migration.
_LEGACY_PATHS = ("src/harness_guard", "scripts/harness-guard")


@dataclass(frozen=True)
class Diagnostic:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str


def run_doctor(repo: Path) -> list[Diagnostic]:
    """Read-only diagnostic of a Codas installation (presence + parse + setup).

    Distinct from ``codas check`` (governance policies): doctor answers "is Codas set
    up correctly here?" so a broken ``.codas`` can be diagnosed before — or when —
    ``check`` cannot run. Deterministic fixed order, read-only; no LLM (§17); imports
    loaders only, never an adapter (§11, the ``codas-app`` boundary). ``fail`` means a
    required input is missing/unparseable; ``warn`` is a non-blocking setup note.
    """
    results: list[Diagnostic] = [_git_repo(repo)]

    config = None
    config_path = repo / ".codas" / "config.yml"
    if not config_path.exists():
        results.append(Diagnostic("config", "fail", f"{_CONFIG} is missing"))
    else:
        try:
            config = load_codas_config(config_path)
            results.append(Diagnostic("config", "ok", f"{_CONFIG} loads"))
        except Exception as error:  # any load/parse failure -> the install is broken
            results.append(Diagnostic("config", "fail", f"{_CONFIG} failed to load: {error}"))

    # Files config declares AUTHORITATIVE are check-required (config_sources emits a
    # `declared-source-missing` ERROR when an authoritative source is absent), so doctor
    # must report their absence as fail, not warn — else it claims OK while `check`
    # fails. policies/waivers/structure are hard-loaded by run_check regardless, so they
    # stay unconditionally required.
    declared = set(config.authoritative_sources) if config is not None else set()

    results.append(_required(repo, _POLICIES, "policies", load_policies))
    results.append(_required(repo, _WAIVERS, "waivers", load_waivers))
    results.append(
        _required(repo, _STRUCTURE, "structure_map", lambda p: load_structure_map(p, source=_STRUCTURE))
    )
    results.append(
        _optional(repo, _PROGRAM, "program_plan", lambda p: load_program_plan(p, source=_PROGRAM), declared)
    )
    results.append(
        _optional(repo, _DOCUMENTS, "documents", lambda p: load_document_manifest(p, source=_DOCUMENTS), declared)
    )
    results.append(_trellis_context(repo, config))
    results.append(_legacy_prototype(repo))
    return results


def doctor_has_failures(diagnostics: list[Diagnostic]) -> bool:
    """True if any diagnostic failed (the ``codas doctor`` non-zero exit condition)."""
    return any(diagnostic.status == "fail" for diagnostic in diagnostics)


def _git_repo(repo: Path) -> Diagnostic:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Diagnostic("git_repo", "warn", "not a git work tree (diff/hooks unavailable)")
    if result.stdout.strip() == "true":
        return Diagnostic("git_repo", "ok", "git work tree")
    return Diagnostic("git_repo", "warn", "not a git work tree (diff/hooks unavailable)")


def _required(
    repo: Path, rel: str, name: str, load: Callable[[Path], object]
) -> Diagnostic:
    path = repo / rel
    if not path.exists():
        return Diagnostic(name, "fail", f"{rel} is missing")
    try:
        load(path)
    except Exception as error:
        return Diagnostic(name, "fail", f"{rel} failed to load: {error}")
    return Diagnostic(name, "ok", f"{rel} loads")


def _optional(
    repo: Path,
    rel: str,
    name: str,
    load: Callable[[Path], object],
    declared_authoritative: set[str],
) -> Diagnostic:
    path = repo / rel
    if not path.exists():
        if rel in declared_authoritative:
            return Diagnostic(
                name, "fail", f"{rel} is declared authoritative in config but is missing"
            )
        return Diagnostic(name, "warn", f"{rel} absent (optional)")
    try:
        load(path)
    except Exception as error:
        return Diagnostic(name, "fail", f"{rel} failed to load: {error}")
    return Diagnostic(name, "ok", f"{rel} loads")


def _trellis_context(repo: Path, config) -> Diagnostic:
    # Mirror check_trellis_context's hard requirement: when the workflow adapter is
    # trellis, the tasks ROOT (<workflow.root>/tasks) must exist — a present .trellis/
    # without tasks/ still fails `check`, so doctor must too.
    if config is None:
        return Diagnostic("trellis_context", "warn", "config did not load; workflow root unknown")
    if config.workflow_adapter != "trellis":
        return Diagnostic("trellis_context", "ok", "no trellis workflow configured")
    root = config.workflow_root or ".trellis"
    tasks_root = repo / root / "tasks"
    if not tasks_root.exists():
        return Diagnostic("trellis_context", "fail", f"trellis tasks root missing: {root}/tasks")
    return Diagnostic("trellis_context", "ok", f"trellis tasks root {root}/tasks present")


def _legacy_prototype(repo: Path) -> Diagnostic:
    present = [path for path in _LEGACY_PATHS if (repo / path).exists()]
    if present:
        return Diagnostic("legacy_prototype", "fail", f"leftover prototype: {', '.join(present)}")
    return Diagnostic("legacy_prototype", "ok", "no legacy prototype leftovers")
