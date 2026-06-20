from __future__ import annotations

import fnmatch

from codas.config.loader import ConfigLoadError, load_claims
from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext

CLAIMS_SOURCE = ".codas/claims.yml"

# NB the call_*/import_* kinds watch OPEN-WORLD fact families (see codas.facts.openworld):
# a call/import added in a form the static extractor does not resolve (dynamic dispatch, a
# module-level call, importlib) produces NO delta and so never fires its coupling. These
# triggers are therefore a LOWER BOUND — they catch the resolved subset, not every real
# co-change. Per the open-world invariant, this gate keys on the PRESENCE of a delta, never
# the absence; symbol_* is tighter than call_*. Surfacing this per-coupling is deferred to
# B4 (the claim schema).
_VALID_KINDS = (
    "symbol_added",
    "symbol_removed",
    "import_added",
    "import_removed",
    "call_added",
    "call_removed",
)


def check_fact_coupling(ctx: ScanContext) -> list[Finding]:
    """Gate fact-level co-change couplings over the working-tree-vs-HEAD fact delta.

    The deterministic gating half of spec-drift v2 (the ``spec-drift-fact-delta``
    thesis: materiality is a STATIC property of an authored coupling, not a per-change
    judgment). A coupling watches a fact-delta predicate and requires a companion path
    to co-change::

        fact_couplings:
          - when_fact:
              kind: symbol_added        # or *_removed; symbol|import|call
              scope: src/codas/policies # repo-rel prefix the fact's module must be under
              name: "check_*"           # optional fnmatch on the fact's identity name
            requires: [src/codas/app/check.py]
            owner: <owner>
            reason: <why the co-change obligation holds>

    A coupling is **always-true by construction**: the trigger is a fact-delta, so a
    change that does not touch the coupled fact (a comment fix, a refactor that adds no
    symbol/import/call) produces no delta and the coupling stays dormant — no semantic
    judgment, no LLM (§17). When the watched delta is nonempty and a required companion
    is absent from the same diff, this fires one error per missing requirement.

    Substrate: ``ctx.fact_delta()`` (symbol/import/call added/removed) and
    ``ctx.changed_paths()`` (files in the diff). BOTH are measured working-tree-vs-HEAD
    against the same working tree, so they share one reference — a fact that changed in
    the working tree and its companion (if it changed) are seen in the same universe.
    This gates the WORKING TREE, not the index: it checks that a required companion is
    PRESENT in the diff, not that it changed semantically (a comment-only edit to the
    companion still satisfies — co-change presence, not correctness; §17 forbids judging
    the latter) and not that the change is staged-only (index isolation is out of scope).
    Consumes facts only via the ScanContext seam — no adapter import (§11). Coupling
    ``scope``/``requires`` paths are normalized (``./`` prefix and backslashes stripped)
    before matching so an author's path spelling cannot silently miss.

    A **malformed** ``fact_couplings`` entry is an ERROR, not a silent skip: a hard gate
    that silently disables itself on a typo is worse than an advisory one. The coarse
    ``must_update_if_changed`` hints in the Structure Map stay advisory (they have no
    always-true fact-level form); an entry graduates to a hard coupling here only when a
    specific fact-delta makes the companion obligation always-true.

    On a clean tree (HEAD == working, nothing staged) the delta is empty, so every
    coupling is dormant and this returns ``[]``. Loads the ``claims.yml`` surface via
    ``config.loader`` (not an adapter, §11-clean; mirrors ``duplicate_implementation``);
    a parse failure yields ``[]`` because ``duplicate_implementation`` already owns the
    canonical claims-load-error finding. Deterministic (total-key sort).
    """
    claims_path = ctx.repo / ".codas" / "claims.yml"
    if not claims_path.exists():
        return []
    try:
        claims_doc = load_claims(claims_path)
    except ConfigLoadError:
        return []  # duplicate_implementation owns the claims-load-error finding

    couplings = claims_doc.get("fact_couplings")
    if couplings is None:
        return []
    if not isinstance(couplings, list):
        return [_malformed("`fact_couplings` must be a list")]

    delta = ctx.fact_delta()
    changed = ctx.changed_paths()

    findings: list[Finding] = []
    for index, entry in enumerate(couplings):
        problem = _schema_problem(entry)
        if problem is not None:
            findings.append(_malformed(f"fact_couplings[{index}]: {problem}"))
            continue
        when = entry["when_fact"]
        kind, scope, name = when["kind"], _norm(when["scope"]), when.get("name")
        if not _delta_has_match(delta, kind, scope, name):
            continue  # watched fact-delta empty -> coupling dormant
        for requirement in entry["requires"]:
            if _any_match(changed, _norm(requirement)):
                continue
            label = f"a `{kind}` fact under '{scope}'"
            if name:
                label += f" matching '{name}'"
            findings.append(
                Finding(
                    severity="error",
                    check_id="fact-coupling",
                    message=(
                        f"{label} requires a co-update of '{requirement}', which is "
                        "not present in this change"
                    ),
                    evidence=[
                        Evidence(
                            path=CLAIMS_SOURCE,
                            detail=f"fact_couplings[{kind} @ {scope}] -> {requirement}",
                        )
                    ],
                    recommendation=(
                        "Update the required companion in the same change, or revise or "
                        "justify the coupling in .codas/claims.yml."
                    ),
                    meta={
                        "kind": kind,
                        "scope": scope,
                        "name": name or "",
                        "requires": requirement,
                        "owner": entry.get("owner") or "",
                        "reason": entry.get("reason") or "",
                    },
                )
            )

    findings.sort(
        key=lambda finding: (
            finding.meta.get("scope", ""),
            finding.meta.get("kind", ""),
            finding.meta.get("requires", ""),
            finding.message,
        )
    )
    return findings


def _schema_problem(entry: object) -> str | None:
    """Return a human reason the coupling entry is malformed, or ``None`` if valid."""
    if not isinstance(entry, dict):
        return "entry must be a mapping"
    when = entry.get("when_fact")
    if not isinstance(when, dict):
        return "`when_fact` must be a mapping"
    if when.get("kind") not in _VALID_KINDS:
        return f"`when_fact.kind` must be one of {list(_VALID_KINDS)}"
    if not isinstance(when.get("scope"), str) or not when.get("scope"):
        return "`when_fact.scope` must be a non-empty string"
    name = when.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        return "`when_fact.name` must be a non-empty string when given"
    requires = entry.get("requires")
    if not isinstance(requires, list) or not requires:
        return "`requires` must be a non-empty list"
    if not all(isinstance(item, str) and item.strip() for item in requires):
        return "`requires` entries must be non-empty strings"
    return None


def _norm(path: str) -> str:
    """Normalize an author-supplied coupling path to repo-relative posix.

    Strips a leading ``./`` and converts backslashes, so a coupling's ``scope`` /
    ``requires`` spelling matches the normalized posix paths Codas facts and
    ``changed_paths`` use — an off-spelling silently missing the match would turn a
    hard gate into a false positive (or silently disable it).
    """
    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    return path.rstrip("/")


def _delta_has_match(delta, kind: str, scope: str, name: str | None) -> bool:
    """True if the ``kind`` delta stream has an entry under ``scope`` matching ``name``."""
    for key in _stream(delta, kind):
        module, identity = _module_and_identity(kind, key)
        if not _under(module, scope):
            continue
        if name is not None and not fnmatch.fnmatch(identity, name):
            continue
        return True
    return False


def _stream(delta, kind: str) -> tuple:
    return {
        "symbol_added": delta.symbols_added,
        "symbol_removed": delta.symbols_removed,
        "import_added": delta.imports_added,
        "import_removed": delta.imports_removed,
        "call_added": delta.calls_added,
        "call_removed": delta.calls_removed,
    }[kind]


def _module_and_identity(kind: str, key: tuple) -> tuple[str, str]:
    """The (module-path, identity-name) a coupling filters on, per fact kind.

    symbol -> (module, name); import -> (importer module, target dotted);
    call -> (caller path, callee symbol).
    """
    if kind.startswith("symbol") or kind.startswith("import"):
        return key[0], key[1]
    return key[0], key[5]  # call: caller_path, callee_symbol


def _under(path: str, scope: str) -> bool:
    scope = scope.rstrip("/")
    return path == scope or path.startswith(scope + "/")


def _any_match(paths: tuple[str, ...], pattern: str) -> bool:
    """True if any changed path equals or fnmatch-globs ``pattern`` (``*`` spans ``/``)."""
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for path in paths)


def _malformed(detail: str) -> Finding:
    return Finding(
        severity="error",
        check_id="fact-coupling",
        message=f"Malformed fact coupling: {detail}",
        evidence=[Evidence(path=CLAIMS_SOURCE)],
        recommendation="Fix the fact_couplings entry schema in .codas/claims.yml.",
        meta={},
    )
