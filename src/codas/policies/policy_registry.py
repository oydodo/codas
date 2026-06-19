from __future__ import annotations

from codas.config.loader import ConfigLoadError, load_policies
from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext

POLICIES_SOURCE = ".codas/policies.yml"
_POLICY_PREFIX = "src/codas/policies/"
_CHECK_PREFIX = "check_"


def check_policy_registry(ctx: ScanContext) -> list[Finding]:
    """Verify .codas/policies.yml declarations match the implemented check_* policies.

    The deterministic ``policy_registry`` coupling (the ``spec-drift-fact-delta`` v2
    PRD's worked example, shipped state-based): the set of policies ``check`` actually
    implements and the set ``policies.yml`` declares must agree, so the declared
    registry can never silently drift from the implementation. A current-state
    set-equality invariant — no diff against HEAD is needed; any change that breaks
    the equality fires, which is v2's fact-delta thesis realized as a state invariant.

    - **implemented** = top-level ``check_<id>`` functions under ``src/codas/policies/``
      (from ``ctx.symbols()``); the id is the FUNCTION name minus ``check_`` — NOT the
      module filename (``missing_owner.py`` defines ``check_missing_structure_owner``).
    - **declared** = keys of the ``policies:`` mapping in ``.codas/policies.yml``. A
      ``status: planned`` entry is a declared-but-not-yet-implemented roadmap policy
      (exempt from needing an impl). ``kind: bootstrap`` is descriptive (a meta/loader
      check, not a governance rule); ``severity`` is the declared/nominal severity, not
      the runtime source (each policy emits its own, sometimes dynamic, severity).

    Findings (error): an implemented check with no declaration; a declared, non-planned
    policy with no implementation. Loads the policies.yml claim surface directly
    (``config.loader``, not an adapter — §11-clean, mirroring how
    ``duplicate_implementation`` loads ``claims.yml``); a parse failure yields ``[]``
    because ``run_check`` already emits ``policy-load-error`` (no double finding).
    Deterministic, no LLM (§17).

    v1 scope (documented in the task PRD): "implemented" = the ``check_*`` symbol
    exists, not that it is wired into ``run_check``; and a top-level helper named
    ``check_*`` inside a policy module would be counted (the convention is one
    ``check_<id>`` entrypoint per module). Both surface as a loud, easily-fixed
    finding, never silent drift; tightening to the check.py import signal is a later
    refinement.
    """
    policies_path = ctx.repo / ".codas" / "policies.yml"
    try:
        raw = load_policies(policies_path)
    except ConfigLoadError:
        return []  # run_check owns the policy-load-error finding; never double-report

    declared = raw.get("policies")
    if not isinstance(declared, dict):
        declared = {}
    # Policy ids are strings; a non-string key (e.g. a YAML `1:` int key) is not a
    # policy and is ignored — also keeps the difference sets homogeneous so the sorts
    # below can't raise on mixed-type comparison (codex impl-review NIT).
    declared_ids = {key for key in declared if isinstance(key, str)}

    # id -> module path (for evidence). Sorted symbol facts make a (never-expected)
    # id collision resolve to the last module deterministically.
    module_of = {
        symbol.name[len(_CHECK_PREFIX):]: symbol.module
        for symbol in ctx.symbols().definitions
        if symbol.kind == "function"
        and symbol.name.startswith(_CHECK_PREFIX)
        and symbol.module.startswith(_POLICY_PREFIX)
    }
    implemented = set(module_of)

    findings: list[Finding] = []
    for policy_id in sorted(implemented - declared_ids):
        findings.append(
            Finding(
                severity="error",
                check_id="policy-registry",
                message=(
                    f"Policy `check_{policy_id}` is implemented but not declared in "
                    f"{POLICIES_SOURCE}."
                ),
                evidence=[Evidence(path=module_of[policy_id])],
                recommendation=(
                    f"Add a `{policy_id}:` entry to {POLICIES_SOURCE} (or remove the "
                    "unused check_ function)."
                ),
            )
        )
    for policy_id in sorted(declared_ids - implemented):
        entry = declared.get(policy_id)
        if isinstance(entry, dict) and entry.get("status") == "planned":
            continue  # declared roadmap policy, intentionally not yet implemented
        findings.append(
            Finding(
                severity="error",
                check_id="policy-registry",
                message=(
                    f"Policy `{policy_id}` is declared in {POLICIES_SOURCE} but has no "
                    f"implementation (no `check_{policy_id}`) and is not marked "
                    "`status: planned`."
                ),
                evidence=[Evidence(path=POLICIES_SOURCE)],
                recommendation=(
                    f"Implement `check_{policy_id}` under {_POLICY_PREFIX}, mark the "
                    "declaration `status: planned`, or remove it."
                ),
            )
        )
    return findings
