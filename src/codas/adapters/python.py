from __future__ import annotations

import ast
import posixpath
from dataclasses import dataclass
from pathlib import Path

from codas.adapters.python_parse import ParsedModules, parse_python_modules


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


@dataclass(frozen=True)
class ImportFact:
    module: str  # importer, repo-relative .py path
    target: str  # absolute dotted module name imported
    target_path: str | None  # repo-rel path of target if first-party, else None
    line: int


@dataclass(frozen=True)
class ImportFacts:
    imports: tuple[ImportFact, ...]
    skipped: tuple[str, ...]


def extract_symbol_facts(repo: Path, files: tuple[str, ...]) -> SymbolFacts:
    """Extract top-level class/function symbol facts from tracked ``.py`` files.

    Back-compat wrapper over :func:`extract_symbol_facts_from_parsed`: parses the
    file set once (the slow path) then projects. Same byte-identical output as
    before; the single-parse seam lives in ``parse_python_modules`` (and is the
    Slice-2 content-hash cache seam).
    """
    return extract_symbol_facts_from_parsed(parse_python_modules(repo, files))


def extract_symbol_facts_from_parsed(parsed: ParsedModules) -> SymbolFacts:
    """Project top-level class/function symbol facts from pre-parsed modules.

    Realizes the §11 Python adapter contract ("Must Emit: symbol facts") using the
    stdlib ``ast`` module — deterministic, no third-party deps, no LLM. Only direct
    module-level definitions are emitted (methods, nested defs and defs inside
    ``if``/``try`` blocks are out of scope); async functions collapse to
    ``"function"``. A file whose parse failed (``tree is None``) is recorded in
    ``skipped`` rather than raising, so a stray file never hard-fails the inventory.
    """
    defs: list[SymbolFact] = []
    skipped: list[str] = []
    for module in parsed.modules:
        if module.tree is None:
            skipped.append(module.path)
            continue
        for node in module.tree.body:  # direct module-level nodes only
            if isinstance(node, ast.ClassDef):
                defs.append(SymbolFact(module.path, node.name, "class", node.lineno))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.append(SymbolFact(module.path, node.name, "function", node.lineno))

    defs.sort(key=lambda fact: (fact.module, fact.line, fact.name, fact.kind))
    return SymbolFacts(tuple(defs), tuple(sorted(skipped)))


def extract_import_facts(repo: Path, files: tuple[str, ...]) -> ImportFacts:
    """Extract import (reference) facts from tracked ``.py`` files.

    Back-compat wrapper over :func:`extract_import_facts_from_parsed` (parses once
    then projects). Same byte-identical output; the single-parse seam is
    ``parse_python_modules``.
    """
    return extract_import_facts_from_parsed(parse_python_modules(repo, files))


def extract_import_facts_from_parsed(parsed: ParsedModules) -> ImportFacts:
    """Project import (reference) facts from pre-parsed modules.

    Realizes the §11 Python adapter contract ("Allowed to know: ... imports") so a
    dependency-direction policy can reason about module edges. Each fact records the
    importer path, the absolute dotted target module, and — when the target resolves
    to a scanned first-party module — that module's repo-relative path (``None`` for
    stdlib/third-party). Relative imports are resolved against the importer's
    package; the file→module map is derived from the ``__init__.py`` package chain
    (no hard-coded source-root prefix). The dotted-name map is built over every
    scanned ``.py`` (parsed or not), exactly as before. Deterministic, no LLM (§17).
    """
    py_files = [module.path for module in parsed.modules]
    package_dirs = {
        posixpath.dirname(f)
        for f in py_files
        if f == "__init__.py" or f.endswith("/__init__.py")
    }
    # Build dotted-name -> path map; sorted iteration + setdefault makes a collision
    # (only possible for stray non-package files) resolve to the first path stably.
    module_paths: dict[str, str] = {}
    for rel in py_files:
        dotted = _dotted_for(rel, package_dirs)
        module_paths.setdefault(dotted, rel)

    facts: list[ImportFact] = []
    skipped: list[str] = []
    for module in parsed.modules:
        if module.tree is None:
            skipped.append(module.path)
            continue
        rel = module.path
        importer = _dotted_for(rel, package_dirs)
        package = importer if rel.endswith("__init__.py") else importer.rpartition(".")[0]
        # One edge per (importer, target); the same target imported on several lines
        # collapses to its first occurrence (smallest line) as evidence.
        first_line: dict[str, int] = {}
        for node in ast.walk(module.tree):
            for target in _targets(node, package, module_paths):
                if target not in first_line or node.lineno < first_line[target]:
                    first_line[target] = node.lineno
        for target in sorted(first_line):
            facts.append(ImportFact(rel, target, module_paths.get(target), first_line[target]))

    facts.sort(key=lambda fact: (fact.module, fact.line, fact.target))
    return ImportFacts(tuple(facts), tuple(sorted(skipped)))


def _dotted_for(path: str, package_dirs: set[str]) -> str:
    """Dotted module name for a repo-relative ``.py`` path via the package chain."""
    directory = posixpath.dirname(path)
    chain: list[str] = []
    current = directory
    while current in package_dirs:
        name = posixpath.basename(current)
        if name:  # a root-level package dir ("") contributes no name segment
            chain.append(name)
        parent = posixpath.dirname(current)
        if parent == current:
            break
        current = parent
    chain.reverse()
    stem = posixpath.basename(path)[: -len(".py")]
    if stem == "__init__":
        return ".".join(chain)
    return ".".join([*chain, stem])


def _resolve_import(module: str, level: int, package: str) -> str | None:
    """Resolve a (possibly relative) import to an absolute dotted name (CPython rule)."""
    if level == 0:
        return module
    parts = package.split(".") if package else []
    if level > len(parts):  # climbs above the top package (CPython: ImportError)
        return None
    base = ".".join(parts[: len(parts) - (level - 1)])
    return f"{base}.{module}" if module else base


def _targets(node: ast.AST, package: str, module_paths: dict[str, str]) -> list[str]:
    """Absolute dotted import targets contributed by one AST node."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        base = _resolve_import(node.module or "", node.level, package)
        if base is None:
            return []
        targets: list[str] = []
        if node.module is not None:
            targets.append(base)
        for alias in node.names:
            dotted = f"{base}.{alias.name}" if base else alias.name
            if dotted in module_paths:  # first-party submodule (never a symbol name)
                targets.append(dotted)
        return targets
    return []
