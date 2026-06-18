from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SymbolFact:
    module: str  # repo-relative .py path
    name: str
    kind: str  # "class" | "function"
    line: int


@dataclass(frozen=True)
class SymbolFacts:
    definitions: tuple[SymbolFact, ...]
    skipped: tuple[str, ...]


def extract_symbol_facts(repo: Path, files: tuple[str, ...]) -> SymbolFacts:
    """Extract top-level class/function symbol facts from tracked ``.py`` files.

    Realizes the §11 Python adapter contract ("Must Emit: symbol facts") using the
    stdlib ``ast`` module — deterministic, no third-party deps, no LLM. Only direct
    module-level definitions are emitted (methods, nested defs and defs inside
    ``if``/``try`` blocks are out of scope); async functions collapse to
    ``"function"``. Unparseable files are recorded in ``skipped`` rather than
    raising, so a stray file never hard-fails the inventory.
    """
    defs: list[SymbolFact] = []
    skipped: list[str] = []
    for rel in sorted(f for f in files if f.endswith(".py")):
        try:
            source = (repo / rel).read_text(errors="ignore")
            tree = ast.parse(source)
        except (OSError, SyntaxError, ValueError):
            skipped.append(rel)
            continue
        for node in tree.body:  # direct module-level nodes only
            if isinstance(node, ast.ClassDef):
                defs.append(SymbolFact(rel, node.name, "class", node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.append(SymbolFact(rel, node.name, "function", node.lineno))

    defs.sort(key=lambda fact: (fact.module, fact.line, fact.name, fact.kind))
    return SymbolFacts(tuple(defs), tuple(sorted(skipped)))
