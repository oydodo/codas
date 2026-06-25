from __future__ import annotations

from difflib import SequenceMatcher

from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext
from codas.policies.anchor_nodes import anchor_call_key, anchor_symbol_node


def _add_path_nodes(nodes: set[str], path: str) -> None:
    """Add a module node (the file path) + its package/dir ancestor nodes, so a
    `contains: <dir>` claim over a real package resolves (matching the tree's package nodes)."""
    nodes.add(path)
    parent = path
    while "/" in parent:
        parent = parent.rsplit("/", 1)[0]
        nodes.add(parent)


def check_code_anchor(ctx: ScanContext) -> list[Finding]:
    """Verify the structural claims of hand-authored Atlas code-wiki pages resolve (code_anchor).

    The deterministic half of the code-wiki: a page under `.codas/wiki/code/**` is advisory
    PROSE (Codas does NOT verify its meaning, and it is kept out of the inventory hash) plus a
    fenced `atlas:claims` block of STRUCTURAL claims. This policy checks ONLY those claims
    against facts.

    Grammar (W5: unified — the former `anchor_symbol` is the `defines`-to-a-top-level-symbol
    case, generalized to the full node-id grammar; `semantic_wiki` folded in here):

      - `defines:  <concept> -> <node-id>`   (concept = UNVERIFIED prose; subject must be a
        known node — a top-level symbol `path::::name`, a class/method `path::cls::sym`, or a
        module/package path)
      - `calls:    <node-id> -> <node-id>`   (must be a known call edge)
      - `contains: <node-id>`                (must be a known node)

    It catches CODE -> DOC drift the user named: a symbol/method renamed or a call edge removed
    makes a committed claim stop resolving — surfaced here so the page gets updated. The
    `doc -> code` direction is left to the Trellis workflow and is not gated here.

    ALL-OPEN severity = WARNING, never an error: the `symbols`/`calls` families are OPEN-world,
    so a non-resolving claim is a lower bound (the code genuinely moved, OR it now takes a
    dynamic/conditional form the static extractor misses — codas.facts.openworld). Per the
    open-world invariant a policy MUST NOT hard-gate on the absence of an open-world fact.

    Resolution universe (self-contained — no `app/` import, no second scan): the node set is
    `ctx.symbols()` (top-level defs as `path::::name`) UNION the `ctx.calls()` endpoints (the
    call-endpoint-derived method nodes the symbol extractor omits but the knowledge tree
    includes) UNION the module + package/dir ancestor nodes of every path — so method-node and
    `contains: <dir>` claims resolve, matching the tree's node universe.

    §11: consumes facts via the ScanContext only (the code-wiki claims + symbols + calls),
    imports no adapter. The page prose never enters the inventory hash (its claims are
    position-stripped policy-time facts), so this policy does not perturb determinism.
    """
    claims = ctx.code_anchor_claims().claims
    if not claims:
        return []

    nodes: set[str] = set()
    for definition in ctx.symbols().definitions:
        nodes.add(f"{definition.module}::::{definition.name}")
        _add_path_nodes(nodes, definition.module)

    edges: set[tuple[str, str]] = set()
    for edge in ctx.calls().edges:
        caller = f"{edge.caller_path}::{edge.caller_class}::{edge.caller_symbol}"
        callee = f"{edge.callee_path}::{edge.callee_class}::{edge.callee_symbol}"
        nodes.add(caller)
        nodes.add(callee)
        _add_path_nodes(nodes, edge.caller_path)
        _add_path_nodes(nodes, edge.callee_path)
        edges.add((caller, callee))

    findings: list[Finding] = []
    for claim in claims:
        if claim.kind == "calls":
            resolves = (claim.subject, claim.object) in edges
            detail = f"{claim.subject} -> {claim.object}"
        else:  # defines / contains
            resolves = claim.subject in nodes
            detail = claim.subject
        if resolves:
            continue
        repair_target = _repair_target(ctx, claim.kind, claim.subject, claim.object)
        if repair_target:
            repair_target = {
                "stale_span": {
                    "path": claim.source,
                    "line": claim.line,
                    "claim_kind": claim.kind,
                    "detail": detail,
                },
                **repair_target,
            }
        meta = {"repair_target": repair_target} if repair_target else {}
        findings.append(
            Finding(
                severity="warning",
                check_id="code-anchor",
                message=(
                    f"code anchor {claim.kind} claim does not resolve: {detail}. "
                    "The node/edge is not in the current facts — the code may have moved "
                    "(update the anchor-bearing doc), OR it now takes a dynamic/conditional "
                    "form the open-world extractor misses (a lower bound; verify by hand)."
                ),
                evidence=[Evidence(path=claim.source, line=claim.line, detail=detail)],
                recommendation="Update the anchor claim, or restore the node/edge.",
                meta=meta,
            )
        )

    findings.sort(
        key=lambda finding: (
            finding.evidence[0].path,
            finding.evidence[0].line or 0,
            finding.evidence[0].detail or "",
        )
    )
    return findings


def _repair_target(ctx: ScanContext, kind: str, subject: str, obj: str) -> dict[str, object] | None:
    if kind in ("defines", "contains"):
        old = anchor_symbol_node(subject)
        if old is None:
            return None
        module, name = old
        removed = [key for key in ctx.fact_delta().symbols_removed if key[0] == module and key[1] == name]
        if not removed:
            return _repair_payload(kind, subject, None, "retarget-subject-node")
        old_kind = removed[0][2]
        best = _best_symbol_candidate(name, old_kind, module, ctx.fact_delta().symbols_added)
        return _repair_payload(kind, subject, best, "retarget-subject-node")
    if kind == "calls":
        old_call = anchor_call_key(subject, obj)
        if old_call is None:
            return None
        if old_call not in ctx.fact_delta().calls_removed:
            return _repair_payload(kind, f"{subject} -> {obj}", None, "retarget-call-edge")
        best_call = _best_call_candidate(old_call, ctx.fact_delta().calls_added)
        return _repair_payload(kind, f"{subject} -> {obj}", best_call, "retarget-call-edge")
    return None


def _repair_payload(
    claim_kind: str,
    old_value: str,
    best_value: str | None,
    action: str,
) -> dict[str, object]:
    return {
        "old_node": {"kind": "call" if claim_kind == "calls" else "symbol", "value": old_value},
        "best_match_new_node": (
            None
            if best_value is None
            else {"kind": "call" if claim_kind == "calls" else "symbol", "value": best_value}
        ),
        "action": action,
    }


def _best_symbol_candidate(
    old_name: str,
    old_kind: str,
    old_module: str,
    added: tuple[tuple[str, str, str], ...],
) -> str | None:
    scored: list[tuple[float, str, str]] = []
    for module, name, kind in added:
        score = SequenceMatcher(None, old_name, name).ratio()
        if module == old_module:
            score += 1.0
        if kind == old_kind:
            score += 0.25
        scored.append((score, module, name))
    if not scored:
        return None
    score, module, name = max(scored, key=lambda item: (item[0], item[1], item[2]))
    if score < 0.75:
        return None
    return f"{module}::::{name}"


def _best_call_candidate(
    old: tuple[str, str, str, str, str, str],
    added: tuple[tuple[str, str, str, str, str, str], ...],
) -> str | None:
    scored: list[tuple[int, tuple[str, str, str, str, str, str]]] = []
    old_caller = old[:3]
    old_callee = old[3:]
    for candidate in added:
        score = 0
        if candidate[:3] == old_caller:
            score += 2
        if candidate[3:] == old_callee:
            score += 2
        if candidate[0] == old[0] or candidate[3] == old[3]:
            score += 1
        if score:
            scored.append((score, candidate))
    if not scored:
        return None
    _score, candidate = max(scored, key=lambda item: (item[0], item[1]))
    return (
        f"{candidate[0]}::{candidate[1]}::{candidate[2]} -> "
        f"{candidate[3]}::{candidate[4]}::{candidate[5]}"
    )
