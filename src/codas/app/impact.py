from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codas.config.loader import load_codas_config
from codas.facts.context import CallFacts, build_scan_context

# ``codas impact <symbol|path>`` — the first P7 agent-query subcommand. Pure reverse
# reachability over the existing deterministic ``calls`` call-graph facts ("changing
# this affects whom"): no new extraction. Facts (and even the ``CallFacts`` type)
# arrive via the ``codas.facts`` seam, never ``codas.adapters`` directly — the §11
# adapter boundary the dependency_direction policy dogfood-enforces. Cycles in the
# call graph terminate on a visited set, exactly like the v3 propagation worklist
# whose single "re-check dependents" hop this is.


@dataclass(frozen=True, order=True)
class _Node:
    """A call-graph node: one caller/callee scope. ``path`` first so ordering (and the
    text report) groups by defining file; ``module`` is functionally implied by
    ``path`` (a first-party file maps to one module) so it never alters the sort."""

    path: str
    cls: str  # "" for a module-level function
    symbol: str
    module: str

    def as_dict(self) -> dict[str, str]:
        return {
            "module": self.module,
            "class": self.cls,
            "symbol": self.symbol,
            "path": self.path,
        }


def _caller_node(edge: Any) -> _Node:
    return _Node(
        path=edge.caller_path,
        cls=edge.caller_class,
        symbol=edge.caller_symbol,
        module=edge.caller_module,
    )


def _callee_node(edge: Any) -> _Node:
    return _Node(
        path=edge.callee_path,
        cls=edge.callee_class,
        symbol=edge.callee_symbol,
        module=edge.callee_module,
    )


def _reverse_graph(calls: CallFacts) -> dict[_Node, set[_Node]]:
    """callee node -> the set of nodes that call it (the reverse of the call graph)."""
    rev: dict[_Node, set[_Node]] = {}
    for edge in calls.edges:
        rev.setdefault(_callee_node(edge), set()).add(_caller_node(edge))
    return rev


def _all_nodes(calls: CallFacts) -> set[_Node]:
    """Every node in the graph (as a caller OR a callee). Lets a symbol that exists
    but has no first-party callers resolve as a found-but-zero-impact target, distinct
    from a target spec that matches nothing."""
    nodes: set[_Node] = set()
    for edge in calls.edges:
        nodes.add(_caller_node(edge))
        nodes.add(_callee_node(edge))
    return nodes


def _norm_path(target: str) -> str:
    cleaned = target.replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def _to_repo_rel(target: str, repo: Path) -> str:
    candidate = Path(target)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo).as_posix()
        except ValueError:
            return _norm_path(target)
    return _norm_path(target)


def _looks_like_path(target: str) -> bool:
    return target.endswith(".py") or "/" in target or "\\" in target


def _symbol_matches(spec: str, node: _Node) -> bool:
    """A symbol target spec matches a node by any natural name form: a bare symbol
    (``head_snapshot``), a class-qualified method (``ScanContext.head_snapshot``), or a
    fully dotted name (``codas.facts.snapshot.head_snapshot`` /
    ``codas.facts.context.ScanContext.head_snapshot``)."""
    candidates = {node.symbol}
    if node.cls:
        candidates.add(f"{node.cls}.{node.symbol}")
        candidates.add(f"{node.module}.{node.cls}.{node.symbol}")
    else:
        candidates.add(f"{node.module}.{node.symbol}")
    return spec in candidates


def _resolve_targets(
    target: str, calls: CallFacts, repo: Path
) -> tuple[str, str, list[_Node]]:
    universe = _all_nodes(calls)
    if _looks_like_path(target):
        rel = _to_repo_rel(target, repo)
        matched = sorted(node for node in universe if node.path == rel)
        return "path", rel, matched
    matched = sorted(node for node in universe if _symbol_matches(target, node))
    return "symbol", target, matched


def _reverse_reach(matched: list[_Node], rev: dict[_Node, set[_Node]]) -> dict[_Node, int]:
    """BFS over reverse edges from the target nodes. ``dist`` doubles as the visited
    set, so a cycle (A calls B calls A) terminates: a node already reached keeps its
    minimum distance and is not re-enqueued. Target nodes sit at distance 0."""
    dist: dict[_Node, int] = {node: 0 for node in matched}
    frontier = sorted(matched)
    depth = 0
    while frontier:
        depth += 1
        nxt: list[_Node] = []
        for node in frontier:
            for caller in sorted(rev.get(node, ())):
                if caller not in dist:
                    dist[caller] = depth
                    nxt.append(caller)
        frontier = sorted(nxt)
    return dist


def compute_impact(calls: CallFacts, target: str, repo: Path) -> dict[str, Any]:
    """Reverse-reachability impact set for ``target`` over the ``calls`` facts.

    Deterministic: every list is sorted, every node is identity-keyed on
    (path, class, symbol, module). ``affected`` is the transitive caller set
    (distance >= 1); the target nodes themselves are excluded.
    """
    kind, norm, matched = _resolve_targets(target, calls, repo)
    rev = _reverse_graph(calls)
    dist = _reverse_reach(matched, rev)
    affected = sorted(node for node, depth in dist.items() if depth >= 1)
    return {
        "target": norm,
        "target_kind": kind,
        "matched": [node.as_dict() for node in matched],
        "affected": [{**node.as_dict(), "distance": dist[node]} for node in affected],
        "affected_paths": sorted({node.path for node in affected}),
    }


def run_impact(repo: Path, target: str) -> dict[str, Any]:
    """Build the per-run ScanContext (scoped exactly like ``codas inventory``) and
    project the impact set from its ``calls`` facts. Read-only: adds no inventory
    facts, mutates nothing."""
    config = load_codas_config(repo / ".codas" / "config.yml")
    ctx = build_scan_context(repo, config)
    return compute_impact(ctx.calls(), target, repo)


def _fqn(node: dict[str, str]) -> str:
    parts = [node["module"]]
    if node["class"]:
        parts.append(node["class"])
    parts.append(node["symbol"])
    return ".".join(parts)


def render_impact_text(result: dict[str, Any]) -> str:
    target = result["target"]
    kind = result["target_kind"]
    matched = result["matched"]
    affected = result["affected"]
    paths = result["affected_paths"]

    lines = [f"impact of {target} ({kind})"]
    if not matched:
        if kind == "path":
            lines.append(
                "  no call-graph symbols for this path "
                "(out of scope, or nothing defined in it is called first-party)."
            )
        else:
            lines.append(
                f"  '{target}' not found in the call graph "
                "(no first-party definition or caller under the scanned roots)."
            )
        return "\n".join(lines)

    lines.append(
        f"  {len(matched)} target symbol(s), "
        f"{len(affected)} affected caller(s) across {len(paths)} file(s)"
    )
    lines.append("")
    lines.append("  target symbols:")
    for node in matched:
        lines.append(f"    {_fqn(node)}  ({node['path']})")
    lines.append("")
    if not affected:
        lines.append("  no first-party callers — changing this affects nothing in scope.")
        return "\n".join(lines)
    lines.append("  affected (transitive callers):")
    for node in affected:
        lines.append(f"    [{node['distance']}] {_fqn(node)}  {node['path']}")
    lines.append("")
    lines.append("  affected files:")
    for path in paths:
        lines.append(f"    {path}")
    return "\n".join(lines)
