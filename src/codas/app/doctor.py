from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from codas.app.agents_block import verify_agents_block
from codas.config.loader import load_codas_config, load_policies, load_waivers
from codas.facts.context import repo_git_baseline
from codas.integrations.claude import verify_claude_shim
from codas.integrations.enforcement import git_hook_status
from codas.integrations.install_state import read_install_state
from codas.integrations.registry import CLAUDE, CODEX, AgentIntegration
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
    loaders + the integration STATUS probes (``codas-app`` MAY depend on
    role-integrations; only ``codas-source``/cli may not), never an adapter (§11).
    ``fail`` means a required input is missing/unparseable; ``warn`` is a non-blocking
    setup note. The hook/freshness diagnostics are WARN-only: absent hooks are the normal
    fresh-clone state (git hooks do not travel with a clone) and the binding staleness gate
    is the CI ``codas agents --verify`` / ``wiki --verify``, not doctor — doctor SEES the
    gate, it is not the gate, and never installs/writes (read-only).
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

    # Gate + injection visibility (gaps 1/4): see whether the git hooks + Claude SessionStart
    # hook are installed and whether the AGENTS block / CLAUDE shim are fresh. WARN-only.
    state = read_install_state(repo)
    results.append(_git_hooks(repo, state))
    # Claude is always probed (the baseline agent + a fresh-clone visibility check). Codex is
    # probed only when opted-in (its install-state slice or .codex/hooks.json exists), so a
    # claude-only repo never sees codex noise.
    results.append(
        _agent_session_diag(
            repo, state, CLAUDE, "agent_hook", "approve workspace-trust in Claude Code", ""
        )
    )
    results.append(_turn_diag(repo, CLAUDE, "turn_hooks", ""))
    results.append(_agents_block(repo))
    results.append(_claude_shim(repo))
    results.extend(_codex_diags(repo, state))

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


def _git_hooks(repo: Path, state: dict) -> Diagnostic:
    """The git enforcement gate: live-probe pre-commit/pre-push. WARN (never fail) when absent —
    git hooks do not travel with a clone, so absence is the normal fresh state; CI gates anyway."""
    status = git_hook_status(repo)
    recorded = state.get("git_hooks") or {}
    absent = sorted(n for n, s in status.items() if s == "absent")
    foreign = sorted(n for n, s in status.items() if s == "foreign")
    installed = sorted(n for n, s in status.items() if s == "installed")
    if not absent and not foreign:
        return Diagnostic("git_hooks", "ok", f"{', '.join(installed)} installed")
    notes: list[str] = []
    if absent:
        # Reconcile live-probe with the install-state marker: a hook recorded installed but now
        # live-absent was removed after install (the payoff of holding both signals).
        gone = [n for n in absent if (recorded.get(n.replace("-", "_")) or {}).get("status") == "installed"]
        note = f"{', '.join(absent)} not installed"
        if gone:
            note += f" ({', '.join(sorted(gone))} recorded installed but file removed)"
        notes.append(note)
    if foreign:
        notes.append(f"{', '.join(foreign)} is a non-Codas hook (pass --force to overwrite)")
    notes.append("run `codas hooks --install`")
    return Diagnostic("git_hooks", "warn", "; ".join(notes))


def _session_slice(state: dict, agent: str) -> dict:
    return (((state.get("agent_hooks") or {}).get(agent) or {}).get("session_start") or {})


def _agent_session_diag(
    repo: Path,
    state: dict,
    integ: AgentIntegration,
    diag_name: str,
    trust_note: str,
    install_suffix: str,
) -> Diagnostic:
    """An agent's SessionStart injection hook. WARN when absent. Surfaces trust: it cannot be
    live-probed, so an installed hook always advises approving trust (hole 4). Parameterised over
    the registry so claude + codex share one probe (codex review N4: no copied logic)."""
    label = integ.name.capitalize()
    status = integ.session_status(repo)
    slice_ = _session_slice(state, integ.name)
    if status == "installed":
        if slice_.get("trusted") is True:
            return Diagnostic(diag_name, "ok", f"{label} SessionStart hook installed + trusted")
        return Diagnostic(
            diag_name, "ok", f"{label} SessionStart hook installed ({trust_note})"
        )
    if status == "malformed":
        return Diagnostic(diag_name, "warn", f"{integ.settings_rel} is malformed")
    detail = f"{label} SessionStart hook not installed — run `codas hooks --install{install_suffix}`"
    if slice_.get("status") == "installed":
        detail = (
            f"{label} SessionStart hook absent (recorded installed but removed) — "
            f"run `codas hooks --install{install_suffix}`"
        )
    return Diagnostic(diag_name, "warn", detail)


def _turn_diag(repo: Path, integ: AgentIntegration, diag_name: str, install_suffix: str) -> Diagnostic:
    """An agent's per-turn injection hooks (gap 3). WARN-only (visibility). Reports how many
    groups are live-installed and — S9 — whether the check is INERT because there is no git
    baseline to diff. ``ok`` only when fully installed AND functional. Parameterised over the
    registry so claude (5 groups) + codex (2 groups) share one probe."""
    specs = integ.turn_specs()
    statuses = {spec.key: integ.hook_status(repo, spec.event, spec.matcher) for spec in specs}
    if any(status == "malformed" for status in statuses.values()):
        return Diagnostic(diag_name, "warn", f"{integ.settings_rel} is malformed")
    installed = sorted(key for key, status in statuses.items() if status == "installed")
    if not installed:
        return Diagnostic(
            diag_name,
            "warn",
            f"per-turn injection hooks not installed — run `codas hooks --install{install_suffix}`",
        )
    detail = f"{len(installed)}/{len(specs)} per-turn injection hooks installed"
    inert = repo_git_baseline(repo) is None
    if inert:
        detail += " — INERT: no git baseline to diff (commit something)"
    healthy = len(installed) == len(specs) and not inert
    return Diagnostic(diag_name, "ok" if healthy else "warn", detail)


def _codex_diags(repo: Path, state: dict) -> list[Diagnostic]:
    """Codex diagnostics — emitted ONLY when Codex is opted-in (its install-state slice exists
    OR ``.codex/hooks.json`` is on disk), so a claude-only repo sees no codex noise. Codex reads
    AGENTS.md natively → no shim diagnostic. The trust note names the Codex repo-trust caveat."""
    opted_in = bool((state.get("agent_hooks") or {}).get("codex")) or (
        repo / CODEX.settings_rel
    ).is_file()
    if not opted_in:
        return []
    return [
        _agent_session_diag(
            repo,
            state,
            CODEX,
            "codex_hook",
            "approve repo-trust: set trust_level=trusted for this project in ~/.codex/config.toml",
            " --agent codex",
        ),
        _turn_diag(repo, CODEX, "codex_turn_hooks", " --agent codex"),
    ]


def _freshness(repo: Path, name: str, filename: str, verify, fix: str) -> Diagnostic:
    """A rendered governance doc's freshness (WARN-only; the binding gate is CI ``--verify``).
    Catch-all so a render/IO error reports rather than crashes the read-only diagnostic."""
    if not (repo / filename).is_file():
        return Diagnostic(name, "warn", f"{filename} missing — run `{fix}`")
    try:
        stale = verify(repo)
    except Exception as error:  # never crash a read-only diagnostic
        return Diagnostic(name, "warn", f"{filename} cannot be rendered: {error}")
    if stale:
        return Diagnostic(name, "warn", f"{filename} stale — run `{fix}`")
    return Diagnostic(name, "ok", f"{filename} fresh")


def _agents_block(repo: Path) -> Diagnostic:
    return _freshness(repo, "agents_block", "AGENTS.md", verify_agents_block, "codas agents --write")


def _claude_shim(repo: Path) -> Diagnostic:
    return _freshness(repo, "claude_shim", "CLAUDE.md", verify_claude_shim, "codas agents --write")


def _legacy_prototype(repo: Path) -> Diagnostic:
    present = [path for path in _LEGACY_PATHS if (repo / path).exists()]
    if present:
        return Diagnostic("legacy_prototype", "fail", f"leftover prototype: {', '.join(present)}")
    return Diagnostic("legacy_prototype", "ok", "no legacy prototype leftovers")
