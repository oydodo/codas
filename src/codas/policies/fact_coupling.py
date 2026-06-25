from __future__ import annotations

import fnmatch
from dataclasses import dataclass

from codas.config.loader import ConfigLoadError, load_claims
from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext
from codas.policies.anchor_nodes import anchor_call_key, anchor_symbol_node

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


@dataclass(frozen=True)
class _Obligation:
    kind: str
    scope: str
    name: str | None
    requirement: str
    evidence_path: str
    evidence_line: int | None
    detail: str
    owner: str = ""
    reason: str = ""
    call_key: tuple[str, str, str, str, str, str] | None = None
    origin: str = "manual"


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
    findings: list[Finding] = []
    obligations: dict[tuple, _Obligation] = {}
    claims_path = ctx.repo / ".codas" / "claims.yml"
    if claims_path.exists():
        try:
            claims_doc = load_claims(claims_path)
        except ConfigLoadError:
            claims_doc = None  # duplicate_implementation owns the claims-load-error finding
        if claims_doc is not None:
            couplings = claims_doc.get("fact_couplings")
            if couplings is not None and not isinstance(couplings, list):
                findings.append(_malformed("`fact_couplings` must be a list"))
            elif isinstance(couplings, list):
                for index, entry in enumerate(couplings):
                    problem = _schema_problem(entry)
                    if problem is not None:
                        findings.append(_malformed(f"fact_couplings[{index}]: {problem}"))
                        continue
                    for obligation in _manual_obligations(entry):
                        obligations[_obligation_key(obligation)] = obligation

    for malformed in ctx.live_doc_anchor_claims().malformed:
        findings.append(
            Finding(
                severity="error",
                check_id="fact-coupling",
                message=f"Malformed live-doc anchor declaration: {malformed.detail}",
                evidence=[
                    Evidence(
                        path=malformed.source,
                        line=malformed.line,
                        detail=malformed.detail,
                    )
                ],
                recommendation="Fix or remove the malformed live-doc anchor line.",
                meta={"origin": "live_doc_anchor"},
            )
        )

    for obligation in _derived_obligations(ctx):
        obligations.setdefault(_obligation_key(obligation), obligation)

    delta = ctx.fact_delta()
    changed = ctx.changed_paths()

    for obligation in obligations.values():
        if not _obligation_matches(delta, obligation):
            continue  # watched fact-delta empty -> coupling dormant
        if _any_match(changed, _norm(obligation.requirement)):
            continue
        label = f"a `{obligation.kind}` fact under '{obligation.scope}'"
        if obligation.name:
            label += f" matching '{obligation.name}'"
        findings.append(
            Finding(
                severity="error",
                check_id="fact-coupling",
                message=(
                    f"{label} requires a co-update of '{obligation.requirement}', which is "
                    "not present in this change"
                ),
                evidence=[
                    Evidence(
                        path=obligation.evidence_path,
                        line=obligation.evidence_line,
                        detail=obligation.detail,
                    )
                ],
                recommendation=(
                    "Update the required companion in the same change, or revise or justify "
                    "the coupling declaration."
                ),
                meta={
                    "kind": obligation.kind,
                    "scope": obligation.scope,
                    "name": obligation.name or "",
                    "requires": obligation.requirement,
                    "owner": obligation.owner,
                    "reason": obligation.reason,
                    "origin": obligation.origin,
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


def _manual_obligations(entry: dict) -> list[_Obligation]:
    when = entry["when_fact"]
    kind, scope, name = when["kind"], _norm(when["scope"]), when.get("name")
    obligations = []
    for requirement in entry["requires"]:
        obligations.append(
            _Obligation(
                kind=kind,
                scope=scope,
                name=name,
                requirement=requirement,
                evidence_path=CLAIMS_SOURCE,
                evidence_line=None,
                detail=f"fact_couplings[{kind} @ {scope}] -> {requirement}",
                owner=entry.get("owner") or "",
                reason=entry.get("reason") or "",
            )
        )
    return obligations


def _derived_obligations(ctx: ScanContext) -> list[_Obligation]:
    out: list[_Obligation] = []
    for claim in ctx.live_doc_anchor_claims().claims:
        if claim.kind == "defines":
            symbol = anchor_symbol_node(claim.subject)
            if symbol is None:
                continue
            module, name = symbol
            for kind in ("symbol_added", "symbol_removed"):
                out.append(
                    _Obligation(
                        kind=kind,
                        scope=module,
                        name=name,
                        requirement=claim.source,
                        evidence_path=claim.source,
                        evidence_line=claim.line,
                        detail=f"{claim.kind}: {claim.subject}",
                        origin="live_doc_anchor",
                    )
                )
        elif claim.kind == "calls":
            call_key = anchor_call_key(claim.subject, claim.object)
            if call_key is None:
                continue
            for kind in ("call_added", "call_removed"):
                out.append(
                    _Obligation(
                        kind=kind,
                        scope=call_key[0],
                        name=call_key[5],
                        requirement=claim.source,
                        evidence_path=claim.source,
                        evidence_line=claim.line,
                        detail=f"calls: {claim.subject} -> {claim.object}",
                        call_key=call_key,
                        origin="live_doc_anchor",
                    )
                )
        elif claim.kind == "contains" and _source_file_path(claim.subject):
            for kind in ("symbol_added", "symbol_removed"):
                out.append(
                    _Obligation(
                        kind=kind,
                        scope=claim.subject,
                        name="[!_]*",
                        requirement=claim.source,
                        evidence_path=claim.source,
                        evidence_line=claim.line,
                        detail=f"contains: {claim.subject}",
                        origin="live_doc_anchor",
                    )
                )
    return out


def _obligation_key(obligation: _Obligation) -> tuple:
    return (
        obligation.kind,
        obligation.scope,
        obligation.name or "",
        obligation.requirement,
        obligation.call_key or (),
    )


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


def _obligation_matches(delta, obligation: _Obligation) -> bool:
    if obligation.call_key is not None:
        return obligation.call_key in _stream(delta, obligation.kind)
    return _delta_has_match(delta, obligation.kind, obligation.scope, obligation.name)


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


def _source_file_path(node: str) -> bool:
    return "::" not in node and node.endswith(".py")


def _malformed(detail: str) -> Finding:
    return Finding(
        severity="error",
        check_id="fact-coupling",
        message=f"Malformed fact coupling: {detail}",
        evidence=[Evidence(path=CLAIMS_SOURCE)],
        recommendation="Fix the fact_couplings entry schema in .codas/claims.yml.",
        meta={},
    )
