from __future__ import annotations

import ast
import posixpath
from dataclasses import dataclass, field
from pathlib import Path

from codas.adapters.python import dotted_for, package_dirs_of
from codas.adapters.python_parse import ParsedModules, parse_python_modules


@dataclass(frozen=True)
class CallFact:
    caller_module: str
    caller_class: str  # "" for a module-level function
    caller_symbol: str
    caller_path: str
    caller_line: int
    callee_module: str
    callee_class: str  # "" for a module-level function
    callee_symbol: str
    callee_path: str
    callee_line: int
    resolution: str  # direct | imported_symbol | module_attribute | self_method


@dataclass(frozen=True)
class CallFacts:
    edges: tuple[CallFact, ...]
    skipped: tuple[str, ...]


def extract_call_facts(repo: Path, files: tuple[str, ...]) -> CallFacts:
    """Deterministic first-party Python call edges via the stdlib ``ast``.

    Pure stdlib (no third-party / no LLM) so the ``calls`` facts stay byte-identical
    across processes — unlike a library such as pyan, whose ambiguous-call resolution
    depends on per-process object ordering. Conservative: emits only edges that
    resolve to a first-party definition, tagged with how it resolved:

    - ``direct``           — ``foo()`` -> a top-level def in the same module
    - ``imported_symbol``  — ``foo()`` -> a ``from pkg.mod import foo`` target
    - ``module_attribute`` — ``mod.foo()`` -> ``foo`` in an imported first-party module
    - ``self_method``      — ``self.m()`` -> method ``m`` of the enclosing class

    Lexical scope is honored: a name rebound locally shadows an import; calls in a
    nested def/class belong to that nested scope, not the enclosing one; ``self.m()``
    resolves to the enclosing class's ``m``. Unresolved/dynamic/builtin calls are
    dropped (not guessed). Fidelity is intentionally lower than a type-resolving
    analyzer (no MRO/super/cross-class instance dispatch); determinism is the
    requirement.

    Back-compat wrapper over :func:`extract_call_facts_from_parsed`: parses the file
    set once then projects. The single-parse seam is ``parse_python_modules``.
    """
    return extract_call_facts_from_parsed(parse_python_modules(repo, files))


def extract_call_facts_from_parsed(parsed: ParsedModules) -> CallFacts:
    """Project deterministic first-party call edges from pre-parsed modules.

    Same contract as :func:`extract_call_facts`; consumes the shared parse instead of
    re-reading. Call-graph scope is narrower than symbols/imports — only ``.py`` files
    that resolve to a package module (``_module_name``) participate; the rest are out
    of scope (not ``skipped``). A parsed-failed file inside a package is ``skipped``.

    Package membership is derived from the parsed file SET (the same
    ``package_dirs_of`` the import extractor uses), NOT the live filesystem — so the
    output is a pure function of (file-set, content). That makes the extractor sound
    for a snapshot taken at any git ref (e.g. ``HEAD``), where the working-tree
    package layout may differ from the ref's, and removes the call graph's last
    working-tree filesystem dependency.
    """
    modules = _modules_from_parsed(parsed)
    by_name = {m.dotted: m for m in modules if not m.error}
    for module in modules:
        if not module.error:
            module.bindings = _bindings(module, by_name)
    skipped = sorted(m.path for m in modules if m.error)

    seen: set[tuple] = set()
    edges: list[CallFact] = []
    for module in modules:
        if module.error:
            continue
        for fact in _module_edges(module, by_name):
            key = (
                fact.caller_path, fact.caller_class, fact.caller_symbol,
                fact.callee_path, fact.callee_class, fact.callee_symbol,
            )
            if key in seen:
                continue
            seen.add(key)
            edges.append(fact)

    edges.sort(
        key=lambda e: (
            e.caller_path, e.caller_class, e.caller_symbol,
            e.callee_path, e.callee_class, e.callee_symbol,
        )
    )
    return CallFacts(edges=tuple(edges), skipped=tuple(skipped))


@dataclass
class _Module:
    path: str
    dotted: str
    is_package: bool
    tree: ast.AST | None
    error: bool
    defs: dict[str, int] = field(default_factory=dict)  # top-level func/class -> line
    classes: dict[str, dict[str, int]] = field(default_factory=dict)  # class -> {method -> line}
    bindings: dict[str, tuple] = field(default_factory=dict)


def _modules_from_parsed(parsed: ParsedModules) -> list[_Module]:
    # Only a READABLE __init__.py marks a package. read_error is the content-pure
    # proxy for the legacy filesystem ``.exists()`` gate: a deleted-but-tracked
    # __init__.py (git ls-files --cached still lists it -> a read_error module here)
    # must NOT put its directory in scope, else this extractor would re-raise that
    # read_error below and crash a dirty repo that the old filesystem walk skipped.
    # A readable-but-unparseable __init__.py (tree=None, read_error=None) still
    # exists, so it still marks the package. At HEAD every blob reads -> no change.
    pkg_dirs = package_dirs_of([m.path for m in parsed.modules if m.read_error is None])
    out: list[_Module] = []
    for parsed_module in parsed.modules:
        rel = parsed_module.path
        dotted = _module_name(rel, pkg_dirs)
        if dotted is None:  # not inside a package -> out of scope
            continue
        is_package = Path(rel).name == "__init__.py"
        if parsed_module.read_error is not None:
            # Legacy read happened inside this extractor and caught only
            # SyntaxError/ValueError, so an OSError propagated. Re-raise it (only for
            # an in-scope package file — out-of-scope files already `continue`d above)
            # to preserve that exact crash semantics rather than silently skip.
            raise parsed_module.read_error
        if parsed_module.tree is None:  # parse failed -> skipped (errored module)
            out.append(_Module(path=rel, dotted=dotted, is_package=is_package, tree=None, error=True))
            continue
        tree = parsed_module.tree
        module = _Module(path=rel, dotted=dotted, is_package=is_package, tree=tree, error=False)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                module.defs.setdefault(node.name, node.lineno)
            elif isinstance(node, ast.ClassDef):
                module.defs.setdefault(node.name, node.lineno)
                methods: dict[str, int] = {}
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.setdefault(item.name, item.lineno)
                module.classes[node.name] = methods
        out.append(module)
    return out


def _module_name(rel: str, package_dirs: set[str]) -> str | None:
    """Dotted module name if ``rel`` lives in a package, else ``None`` (out of scope).

    The package gate and the dotted name are both derived from ``package_dirs`` (the
    set of directories holding an ``__init__.py`` in the scanned file set), matching
    the import extractor's ``dotted_for``. This replaces the previous working-tree
    ``(repo/rel).parent / "__init__.py"`` stat, so the call graph no longer reads the
    live filesystem. The gate is unchanged in meaning — the file's own directory must
    be a package — and the dotted name is the same package-chain walk, now bounded by
    the repo (the old absolute-path walk could climb above the repo root).
    """
    if posixpath.dirname(rel) not in package_dirs:
        return None
    return dotted_for(rel, package_dirs)


def _bindings(module: _Module, by_name: dict[str, _Module]) -> dict[str, tuple]:
    out: dict[str, tuple] = {}
    for node in ast.walk(module.tree):
        if isinstance(node, ast.ImportFrom):
            target = _resolve_from(node.module, node.level, module)
            if target is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                sub = f"{target}.{alias.name}"
                if sub in by_name:  # `from pkg import submodule`
                    out[local] = ("module", sub)
                elif target in by_name and alias.name in by_name[target].defs:
                    out[local] = ("symbol", target, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in by_name:
                    local = alias.asname or alias.name.split(".")[0]
                    out[local] = ("module", alias.name)
    return out


def _resolve_from(module: str | None, level: int, importer: _Module) -> str | None:
    """Resolve an ``ImportFrom`` to an absolute dotted module name.

    The anchor for a relative import is the importer's *package*: for a package file
    (``pkg/__init__.py`` -> dotted ``pkg``) that is the importer itself; for a module
    (``pkg.mod``) it is ``pkg``. ``level`` then climbs from there.
    """
    if level == 0:
        return module
    package = importer.dotted if importer.is_package else importer.dotted.rsplit(".", 1)[0]
    parts = package.split(".") if package else []
    if level - 1 > len(parts):
        return None
    base = parts[: len(parts) - (level - 1)]
    if module:
        base = base + module.split(".")
    return ".".join(base) if base else None


def _local_names(scope: ast.AST) -> set[str]:
    """Names bound locally in a scope (params + assignment targets), which shadow
    module-level imports/defs. Nested def/class scopes are not descended."""
    names: set[str] = set()
    args = getattr(scope, "args", None)
    if args is not None:
        for group in (args.posonlyargs, args.args, args.kwonlyargs):
            for arg in group:
                names.add(arg.arg)
        for arg in (args.vararg, args.kwarg):
            if arg is not None:
                names.add(arg.arg)
    for node in _walk_scope(scope):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def _walk_scope(scope: ast.AST):
    """Yield nodes inside a scope's body, NOT descending into nested def/class."""
    for stmt in getattr(scope, "body", []):
        yield from _walk_no_nested(stmt)


def _walk_no_nested(node: ast.AST):
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield from _walk_no_nested(child)


def _module_edges(module: _Module, by_name: dict[str, _Module]) -> list[CallFact]:
    facts: list[CallFact] = []

    def emit(caller_class, caller_sym, caller_line, call, locals_):
        resolved = _resolve_call(call, module, by_name, caller_class, locals_)
        if resolved is None:
            return
        cmod, ccls, csym, cpath, cline, kind = resolved
        facts.append(
            CallFact(
                caller_module=module.dotted, caller_class=caller_class,
                caller_symbol=caller_sym, caller_path=module.path, caller_line=caller_line,
                callee_module=cmod, callee_class=ccls, callee_symbol=csym,
                callee_path=cpath, callee_line=cline, resolution=kind,
            )
        )

    def process(scope, caller_class, caller_sym, caller_line):
        locals_ = _local_names(scope)
        for node in _walk_scope(scope):
            if isinstance(node, ast.Call):
                emit(caller_class, caller_sym, caller_line, node, locals_)

    for node in getattr(module.tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            process(node, "", node.name, node.lineno)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    process(item, node.name, item.name, item.lineno)
    return facts


def _resolve_call(call, module, by_name, caller_class, locals_):
    func = call.func
    if isinstance(func, ast.Name):
        name = func.id
        if name in locals_:  # shadowed by a local binding -> not the import/def
            return None
        binding = module.bindings.get(name)
        if binding and binding[0] == "symbol":
            _, tmod, tsym = binding
            target = by_name.get(tmod)
            if target and tsym in target.defs:
                return (tmod, "", tsym, target.path, target.defs[tsym], "imported_symbol")
        if name in module.defs:
            return (module.dotted, "", name, module.path, module.defs[name], "direct")
    elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base, attr = func.value.id, func.attr
        if base == "self" and caller_class:
            methods = module.classes.get(caller_class, {})
            if attr in methods:
                return (module.dotted, caller_class, attr, module.path, methods[attr], "self_method")
        if base not in locals_:
            binding = module.bindings.get(base)
            if binding and binding[0] == "module":
                target = by_name.get(binding[1])
                if target and attr in target.defs:
                    return (binding[1], "", attr, target.path, target.defs[attr], "module_attribute")
    return None
