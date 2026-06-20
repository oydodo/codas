from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.app.wiki import build_atlas_pack, build_atlas_tree
from codas.facts.openworld import open_world_gaps

# W3·S1 — deterministic, LLM-free VIEWS over the verified facts ("borrow CodeWiki's mermaid +
# html, the Codas way"): a Mermaid product-module dependency graph and a static HTML viewer,
# both PURE projections of the Atlas pack + Block A knowledge tree. Printed to stdout, never in
# the inventory hash. CRITICAL: each view RENDERS the open-world caveat into its output — a
# dependency picture that hides "this is a sound LOWER BOUND, absence != denial" would
# re-import a false-completeness failure at the presentation layer (mirrors `codas impact`).

_IMPORT_CAVEAT = (
    "OPEN-WORLD: this import graph is a sound LOWER BOUND — a missing edge is not proof of "
    "no import (absence is not denial). Misses: "
)


def _import_caveat() -> str:
    return _IMPORT_CAVEAT + "; ".join(open_world_gaps("imports"))


def _mermaid_label(text: str) -> str:
    """A Mermaid-safe quoted-label body. Beyond the quote/newline that break the `["..."]`
    label, also neutralize the bracket/angle/backtick chars that break Mermaid node syntax
    (real module paths never contain these, but a synthetic/adversarial path could).
    Deterministic substitution, never a crash."""
    out = text.replace("\\", "/").replace('"', "'").replace("`", "'")
    out = out.replace("[", "(").replace("]", ")").replace("<", "(").replace(">", ")")
    return out.replace("\n", " ").replace("\r", " ")


def build_mermaid(repo: Path) -> str:
    """A Mermaid `graph LR` of the PRODUCT module dependency graph (import facts), with the
    open-world caveat as a `%%` comment AND a visible note node. Deterministic: nodes are
    sorted and id'd by sorted position; edges follow the pack's already-sorted order."""
    edges = build_atlas_pack(repo)["dependency_graph"]
    nodes = sorted({e["module"] for e in edges} | {e["target_path"] for e in edges})
    node_id = {path: f"n{i}" for i, path in enumerate(nodes)}

    lines = [
        "%% codas wiki --emit-mermaid — product module dependency graph (import facts).",
        "%% " + _import_caveat(),
        "graph LR",
    ]
    for path in nodes:
        lines.append(f'  {node_id[path]}["{_mermaid_label(path)}"]')
    # re-sort edges locally on a total key so output never depends on the upstream pack's
    # sort guarantee staying stable.
    for edge in sorted(
        edges, key=lambda e: (e["module"], e["target_path"], e["target"])
    ):
        lines.append(f"  {node_id[edge['module']]} --> {node_id[edge['target_path']]}")
    # the caveat is also a VISIBLE node, so a rendered diagram never reads as complete.
    lines.append(f'  owCaveat["{_mermaid_label(_import_caveat())}"]')
    return "\n".join(lines) + "\n"


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _tree_roots(tree: dict[str, Any]) -> list[str]:
    all_children: set[str] = set()
    for node in tree.values():
        all_children.update(node.get("children") or ())
    return sorted(nid for nid in tree if nid not in all_children)


def _render_nav(
    tree: dict[str, Any], node_id: str, depth: int, seen: set[str] | None = None
) -> list[str]:
    if seen is None:
        seen = set()
    node = tree.get(node_id)
    if node is None or node_id in seen:
        return []  # cycle/revisit guard (the Block A tree is acyclic; this is defensive)
    seen.add(node_id)
    pad = "  " * depth
    owner = node.get("unit_owner")
    owner_html = f' <span class="owner">[{_html_escape(owner)}]</span>' if owner else ""
    head = (
        f'{pad}<li><code>{_html_escape(node_id)}</code> '
        f'<em>{_html_escape(node["kind"])}</em>{owner_html}'
    )
    children = node.get("children") or []
    if not children:
        return [head + "</li>"]
    out = [head, f"{pad}<ul>"]
    for child in children:  # already sorted in the tree
        out += _render_nav(tree, child, depth + 1, seen)
    out += [f"{pad}</ul>", f"{pad}</li>"]
    return out


def build_html(repo: Path) -> str:
    """A self-contained static HTML view: the open-world caveat banner, the Mermaid diagram
    SOURCE, and a navigable knowledge tree (packages -> modules -> symbols, with unit
    ownership). A pure, deterministic projection. Deliberately loads NO external script (no
    CDN dependency / no Subresource-Integrity surface / no network at view time) — the
    diagram is rendered as copy-paste Mermaid source, consistent with Codas's zero-external-
    dependency, self-contained ethos."""
    mermaid = build_mermaid(repo)
    tree = build_atlas_tree(repo)["tree"]
    nav: list[str] = []
    for root in _tree_roots(tree):
        nav += _render_nav(tree, root, 0)

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>Codas Atlas View (verified facts)</title>",
            "<style>",
            "body{font-family:system-ui,sans-serif;margin:2rem;max-width:60rem}",
            ".caveat{background:#fff3cd;border:1px solid #e0c75a;padding:.75rem 1rem;"
            "border-radius:.4rem;margin:1rem 0}",
            ".owner{color:#666;font-size:.85em}",
            "code{background:#f4f4f4;padding:.1em .3em;border-radius:.2em}",
            "pre.mermaid{background:#f4f4f4;padding:1rem;border-radius:.4rem;overflow:auto}",
            "ul{list-style:none}",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Codas Atlas View <small>(generated; verified facts)</small></h1>",
            f'<div class="caveat">{_html_escape(_import_caveat())}</div>',
            "<h2>Module dependency graph</h2>",
            "<p>Mermaid source (paste into any Mermaid renderer; no external script is "
            "loaded by this page):</p>",
            f'<pre class="mermaid">\n{_html_escape(mermaid)}</pre>',
            "<h2>Knowledge tree</h2>",
            "<ul>",
            *nav,
            "</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )
