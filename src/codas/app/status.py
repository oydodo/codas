"""``codas status`` — per-turn injection (gap 3): JIT, advisory feedback on the files
changed this session, BEFORE the commit gate.

The neutral, platform-agnostic core. It derives the changed-file set from git (the
session baseline, falling back to the working-tree diff), runs only the CHEAP policy
subset that a name-level check needs — ``missing_structure_owner`` /
``deprecated_path_used`` / ``duplicate_symbol`` — and FILTERS findings to the changed
files. It never triggers the expensive cross-file resolution the gate's
``dependency_direction`` / ``duplicate_implementation`` / ``fact_coupling`` need, so it
stays fast enough to run on every agent turn.

§11/§17: reuses the real policy functions (``codas-policies``) + the facts seam
(``codas-facts``); no adapter import, no LLM, no judgement. The findings are FACTUAL
statements (never imperative recommendations) — the injected text reaches a coding agent,
and an out-of-band imperative trips its prompt-injection defence. The Claude-specific hook
envelope lives in ``integrations/claude``; this module emits only neutral text/JSON.

Determinism note: this command is NOT wired into ``check`` or ``inventory`` and its scratch
state (``.codas/.status-seen.json``) is gitignored + in ``structure.index._IGNORE_PATHS``,
so it can never perturb the byte-identical inventory hash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from codas.config.loader import load_codas_config
from codas.core.models import Finding
from codas.facts.context import build_scan_context, repo_git_baseline
from codas.policies.deprecated_path import check_deprecated_path_used
from codas.policies.duplicate_symbol import check_duplicate_symbol
from codas.policies.missing_owner import check_missing_structure_owner

# Machine-local scratch holding the session BASELINE sha + the set of already-injected
# finding fingerprints. Gitignored AND in structure.index._IGNORE_PATHS (like
# .install-state.json), so a write never moves the byte-identical inventory hash.
STATUS_STATE_PATH = ".codas/.status-seen.json"
_STATE_SCHEMA = 1

# S3 — hard-cap the injected payload. missing_owner emits one finding per unowned
# artifact, re-surfaced every turn; an uncapped flood would erode the very context window
# per-turn injection exists to protect. Bounds are asserted by tests, not just prose.
_MAX_LINES = 10
_MAX_BYTES = 2000


@dataclass(frozen=True)
class StatusResult:
    """The outcome of one ``codas status`` run.

    ``findings`` — sorted ``{path, kind, message}`` dicts, factual (no recommendation).
    ``git`` — ``ok`` (diffable) | ``no-baseline`` (not a repo / no commits — the hook is
    INERT, not silently clear) | ``stale-baseline`` (a ``--since`` ref that no longer resolves,
    so the run degraded to the working-tree diff only) | ``error`` (the run guard swallowed an
    exception). ``affected_count`` — size of the changed-file set the findings were filtered to.
    """

    findings: tuple[dict, ...]
    git: str
    affected_count: int


def run_status(
    repo: Path, paths: tuple[str, ...] = (), since: str | None = None
) -> StatusResult:
    """Compute changed-file findings. NEVER raises (S5): any failure → an empty result
    with ``git="error"`` so a hook can run it on every turn without ever blocking one."""
    try:
        return _run_status(repo, tuple(paths), since)
    except Exception:  # noqa: BLE001 — status must never crash the turn it advises.
        return StatusResult(findings=(), git="error", affected_count=0)


def _run_status(repo: Path, paths: tuple[str, ...], since: str | None) -> StatusResult:
    config = load_codas_config(repo / ".codas" / "config.yml")
    ctx = build_scan_context(repo, config)

    git_state = "ok" if ctx.git_baseline() is not None else "no-baseline"

    # The changed-file set: the working-tree diff, plus everything changed since the
    # session baseline (committed-by-a-worker changes the working tree is blind to — B1).
    affected = set(ctx.changed_paths())
    if since:
        # A stale/orphaned baseline (rebase/squash) silently contributes nothing; surface it
        # rather than masquerading as a clean working tree (S2/S9). The run still degrades to
        # the working-tree diff, and the next SessionStart re-records a fresh baseline.
        if git_state == "ok" and not ctx.ref_resolves(since):
            git_state = "stale-baseline"
        else:
            affected |= set(ctx.changed_since(since))
    if paths:
        wanted = [p.strip("/") for p in paths if p.strip("/")]
        affected = {
            a for a in affected if any(a == p or a.startswith(p + "/") for p in wanted)
        }

    rows: list[dict] = []
    rows += _artifact_findings(check_missing_structure_owner(repo, config), affected)
    rows += _artifact_findings(check_deprecated_path_used(repo, config), affected)
    rows += _duplicate_findings(check_duplicate_symbol(ctx), affected)

    # Deterministic order + de-dupe identical rows (a path can be both unowned and under a
    # deprecated prefix, but two policies never emit the same (path, kind, message)).
    rows.sort(key=lambda r: (r["path"], r["kind"], r["message"]))
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for row in rows:
        key = (row["path"], row["kind"], row["message"])
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return StatusResult(tuple(unique), git_state, len(affected))


def _artifact_findings(findings: list[Finding], affected: set[str]) -> list[dict]:
    """``missing_owner`` / ``deprecated_path`` each carry the artifact as ``evidence[0]``;
    keep the finding iff that artifact is in the changed-file set. The message is the
    policy's own factual message — the imperative ``recommendation`` is dropped (S1)."""
    out: list[dict] = []
    for finding in findings:
        path = finding.evidence[0].path if finding.evidence else None
        if path is not None and path in affected:
            out.append(
                {"path": path, "kind": finding.check_id, "message": finding.message}
            )
    return out


def _duplicate_findings(findings: list[Finding], affected: set[str]) -> list[dict]:
    """The precise, status-specific predicate for duplicate-symbol (B2): a finding enters
    status iff a symbol DEFINED in an affected file ALSO exists in another module — i.e.
    the change touched one side of an existing name collision (not an unrelated, untouched
    pre-existing dup). Emitted once per affected defining module, with a self-contained
    factual message (no imperative).

    NB ``duplicate_symbol`` is scoped to public, top-level ``src/`` symbols (its own
    ``SCOPE_PREFIX``); on a non-``src/`` layout status reports zero duplicate findings.
    That src-only limitation is intentional for the MVP (it matches the policy's scope)
    and is pinned by a test."""
    out: list[dict] = []
    for finding in findings:
        modules = list(finding.meta.get("modules") or [])
        name = finding.meta.get("name")
        for module in modules:
            if module in affected:
                others = [m for m in modules if m != module]
                out.append(
                    {
                        "path": module,
                        "kind": "duplicate-symbol",
                        "message": (
                            f"{module}: public symbol '{name}' is also defined in "
                            f"{', '.join(others)}"
                        ),
                    }
                )
    return out


def render_text(result: StatusResult) -> str:
    """Human-readable summary for a manual ``codas status`` / CI run (uncapped)."""
    if result.git == "no-baseline":
        return (
            "codas status: no git baseline (not a repo, or no commits) — "
            "nothing to diff."
        )
    prefix = ""
    if result.git == "stale-baseline":
        prefix = (
            "codas status: the --since baseline did not resolve — "
            "showing the working-tree diff only.\n"
        )
    if not result.findings:
        return prefix + "codas status: no findings on changed files."
    lines = [f"codas status: {len(result.findings)} finding(s) on changed files:"]
    lines += [f"- {row['message']}" for row in result.findings]
    return prefix + "\n".join(lines)


_ADVISORY_HEADER = "Codas (advisory) — facts about files changed this session:"


def _shown_rows(
    findings: tuple[dict, ...], *, lines_cap: int = _MAX_LINES, bytes_cap: int = _MAX_BYTES
) -> list[dict]:
    """The findings that ACTUALLY fit the line + byte cap (S3) — the exact rows injected.

    Shared by ``render_additional_context`` (to format) and ``inject_context`` (to persist
    exactly the surfaced rows). A single over-budget row is SKIPPED, not a barrier, so one
    pathologically large finding cannot suppress the smaller ones after it; capped-out rows
    are simply not returned, so they stay unseen and surface on a later turn (S2 × S3)."""
    header_cost = len(_ADVISORY_HEADER.encode("utf-8"))
    size = header_cost
    shown: list[dict] = []
    for row in findings[:lines_cap]:
        cost = len(f"- {row['message']}".encode("utf-8")) + 1  # +1 for the joining newline
        if size + cost > bytes_cap:
            continue
        size += cost
        shown.append(row)
    return shown


def render_additional_context(
    result: StatusResult, *, lines_cap: int = _MAX_LINES, bytes_cap: int = _MAX_BYTES
) -> str:
    """The capped, factual advisory string a platform shim wraps as ``additionalContext``.

    Empty string when there is nothing to surface (clean / no findings / no baseline / error /
    nothing fits the byte cap) — the shim then injects nothing (never a header-only payload).
    The cap (S3) is a hard, tested invariant: at most ``lines_cap`` finding lines and
    ``bytes_cap`` bytes, with a ``+K more`` tail so a truncation is never silent.
    """
    shown = _shown_rows(result.findings, lines_cap=lines_cap, bytes_cap=bytes_cap)
    if not shown:
        return ""
    out = [_ADVISORY_HEADER] + [f"- {row['message']}" for row in shown]
    remaining = len(result.findings) - len(shown)
    if remaining > 0:
        out.append(f"- (+{remaining} more — run `codas status`)")
    return "\n".join(out)


# --- session scratch state: baseline sha + injected-finding fingerprints (B1 + S2) ------


def _fingerprint(row: dict) -> str:
    """Stable id of an injected finding (path+kind+message), so a standing finding is
    surfaced once per session, not re-injected on every return (S2)."""
    raw = f"{row['path']}\0{row['kind']}\0{row['message']}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _read_state(repo: Path) -> dict:
    path = repo / STATUS_STATE_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(repo: Path, data: dict) -> None:
    path = repo / STATUS_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def read_baseline(repo: Path) -> str | None:
    """The recorded session baseline sha (or ``None``) — what ``--since-baseline`` diffs
    against."""
    value = _read_state(repo).get("baseline")
    return value if isinstance(value, str) else None


def record_baseline(repo: Path) -> str | None:
    """Record the current ``HEAD`` as the session baseline ``--since-baseline`` diffs
    against, and RESET the injected-finding set (a new session does not inherit the
    previous one's suppressions). Called by the SessionStart hook. Returns the sha, or
    ``None`` when there is no git baseline. Never raises."""
    try:
        sha = repo_git_baseline(repo)
        state = _read_state(repo)
        state["schema_version"] = _STATE_SCHEMA
        state["baseline"] = sha
        state["seen"] = []
        _write_state(repo, state)
        return sha
    except Exception:  # noqa: BLE001 — baseline recording must never crash a session start.
        return None


def inject_context(repo: Path, *, use_baseline: bool = True) -> str:
    """The hook entrypoint: compute changed-file findings (since the recorded session
    baseline when available), SUPPRESS already-injected ones, PERSIST the new
    fingerprints, and return the capped factual ``additionalContext`` string (``""`` →
    inject nothing). NEVER raises (S5)."""
    try:
        state = _read_state(repo)
        baseline = state.get("baseline") if use_baseline else None
        result = run_status(repo, since=baseline if isinstance(baseline, str) else None)
        already = set(state.get("seen") or [])
        fresh = tuple(row for row in result.findings if _fingerprint(row) not in already)
        fresh_result = StatusResult(fresh, result.git, result.affected_count)
        # Persist ONLY the rows actually injected (S1×S3): a finding capped out of this turn's
        # payload stays unseen and surfaces on a later turn once the shown ones clear, instead
        # of being marked seen and silently dropped forever.
        shown = _shown_rows(fresh)
        text = render_additional_context(fresh_result)
        if shown:
            state["schema_version"] = _STATE_SCHEMA
            state["seen"] = sorted(already | {_fingerprint(row) for row in shown})
            _write_state(repo, state)
        return text
    except Exception:  # noqa: BLE001 — injection must never crash the turn it advises.
        return ""
