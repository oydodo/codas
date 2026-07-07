from __future__ import annotations

from typing import Any

from codas.adapters.python import ImportFact, ImportFacts, SymbolFact, SymbolFacts
from codas.adapters.references import (
    DefinitionRecord,
    ReferenceCandidate,
    resolve_reference_edges,
)
from codas.adapters.swift_parse import ParsedSwiftModules

_CLASS_DECL_KINDS = {"class", "struct", "enum", "extension", "actor"}
_DECLARATION_KINDS = {
    "protocol_declaration": "protocol",
    "function_declaration": "function",
    "typealias_declaration": "typealias",
}


def extract_swift_symbols(parsed: ParsedSwiftModules) -> SymbolFacts:
    """Extract gate-grade top-level Swift symbol facts from parsed modules."""
    definitions: list[SymbolFact] = []
    skipped: list[str] = []
    for module in parsed.modules:
        if module.tree is None:
            skipped.append(module.path)
            continue
        skipped.extend(_parse_error_reasons(module))
        for node in module.tree.root_node.children:
            if _node_is_error(node):
                continue
            fact = _symbol_for_node(module.path, module.source, node)
            if fact is not None:
                definitions.append(fact)
    definitions.sort(key=lambda fact: (fact.module, fact.line, fact.name, fact.kind))
    return SymbolFacts(tuple(definitions), tuple(sorted(skipped)))


def extract_swift_imports(parsed: ParsedSwiftModules) -> ImportFacts:
    """Extract Swift module imports plus unique first-party type-reference edges."""
    imports: list[ImportFact] = []
    skipped: list[str] = []
    for module in parsed.modules:
        if module.tree is None:
            skipped.append(module.path)
            continue
        skipped.extend(_parse_error_reasons(module))
        first_line: dict[str, int] = {}
        for node in module.tree.root_node.children:
            if _node_is_error(node):
                continue
            if node.type != "import_declaration":
                continue
            target = _import_target(module.source, node)
            if not target:
                continue
            line = _line(node)
            if target not in first_line or line < first_line[target]:
                first_line[target] = line
        for target in sorted(first_line):
            imports.append(ImportFact(module.path, target, None, first_line[target]))

    reference_edges = resolve_reference_edges(
        _swift_type_definitions(parsed), _swift_reference_candidates(parsed)
    )
    imports.extend(reference_edges.imports)
    imports = _dedupe_imports(imports)
    return ImportFacts(tuple(imports), tuple(sorted(skipped)))


def _symbol_for_node(path: str, source: bytes, node: Any) -> SymbolFact | None:
    if node.type == "class_declaration":
        kind = _class_decl_kind(node)
        if kind is None or kind == "extension":
            return None
    else:
        kind = _DECLARATION_KINDS.get(node.type)
        if kind is None:
            return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(source, name_node)
    if not name:
        return None
    return SymbolFact(path, name, kind, _line(node))


def _swift_type_definitions(parsed: ParsedSwiftModules) -> tuple[DefinitionRecord, ...]:
    definitions: list[DefinitionRecord] = []
    for module in parsed.modules:
        if module.tree is None:
            continue
        for node in module.tree.root_node.children:
            fact = _symbol_for_node(module.path, module.source, node)
            if fact is None or fact.kind == "function":
                continue
            definitions.append(
                DefinitionRecord(
                    name=fact.name,
                    qualified_name=fact.name,
                    module=module.path,
                    path=module.path,
                    kind=fact.kind,
                    line=fact.line,
                )
            )
    return tuple(
        sorted(
            definitions,
            key=lambda item: (item.path, item.line, item.qualified_name, item.kind),
        )
    )


def _swift_reference_candidates(parsed: ParsedSwiftModules) -> tuple[ReferenceCandidate, ...]:
    candidates: list[ReferenceCandidate] = []
    seen: set[tuple[str, str, int, str]] = set()
    for module in parsed.modules:
        if module.tree is None:
            continue
        for node in _walk(module.tree.root_node):
            if node.type != "type_identifier":
                continue
            if _is_swift_definition_name(node) or _is_under(node, {"import_declaration", "type_parameter"}):
                continue
            if not _is_explicit_type_reference(node):
                continue
            name = _text(module.source, node)
            if not name:
                continue
            line = _line(node)
            key = (module.path, name, line, _syntax_kind(node))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                ReferenceCandidate(
                    name=name,
                    qualified_name=None,
                    module=module.path,
                    path=module.path,
                    line=line,
                    syntax_kind=_syntax_kind(node),
                )
            )
    return tuple(
        sorted(candidates, key=lambda item: (item.path, item.line, item.name, item.syntax_kind))
    )


def _walk(node: Any):
    if _node_is_error(node):
        return
    yield node
    for child in getattr(node, "children", ()):
        yield from _walk(child)


def _node_is_error(node: Any) -> bool:
    return node.type == "ERROR" or bool(getattr(node, "is_missing", False))


def _parse_error_reasons(module: Any) -> list[str]:
    return [
        error.as_skipped_reason(module.path)
        for error in getattr(module, "parse_errors", ())
    ]


def _is_swift_definition_name(node: Any) -> bool:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if parent.type in {"class_declaration", "protocol_declaration", "typealias_declaration"}:
            try:
                if parent.child_by_field_name("name") == node:
                    return True
            except Exception:
                return False
        parent = getattr(parent, "parent", None)
    return False


def _is_under(node: Any, types: set[str]) -> bool:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if parent.type in types:
            return True
        parent = getattr(parent, "parent", None)
    return False


def _is_explicit_type_reference(node: Any) -> bool:
    reference_contexts = {
        "array_type",
        "dictionary_type",
        "function_type",
        "generic_type",
        "inheritance_clause",
        "metatype",
        "optional_type",
        "protocol_function_declaration",
        "protocol_property_declaration",
        "some_or_any_type",
        "tuple_type",
        "type_annotation",
        "type_identifier",
        "typealias_declaration",
        "user_type",
    }
    return _is_under(node, reference_contexts)


def _syntax_kind(node: Any) -> str:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if parent.type in {
            "inheritance_clause",
            "type_annotation",
            "typealias_declaration",
            "user_type",
        }:
            return parent.type
        parent = getattr(parent, "parent", None)
    return "type_reference"


def _dedupe_imports(imports: list[ImportFact]) -> list[ImportFact]:
    first_line: dict[tuple[str, str, str | None], int] = {}
    for fact in imports:
        key = (fact.module, fact.target, fact.target_path)
        if key not in first_line or fact.line < first_line[key]:
            first_line[key] = fact.line
    return sorted(
        (
            ImportFact(module=module, target=target, target_path=target_path, line=line)
            for (module, target, target_path), line in first_line.items()
        ),
        key=lambda fact: (fact.module, fact.line, fact.target, fact.target_path or ""),
    )


def _class_decl_kind(node: Any) -> str | None:
    for child in node.children:
        if child.type in _CLASS_DECL_KINDS:
            return child.type
    return None


def _import_target(source: bytes, node: Any) -> str:
    for child in node.named_children:
        text = _text(source, child)
        if text:
            return text
    text = _text(source, node).strip()
    if text.startswith("import "):
        return text[len("import "):].strip()
    return ""


def _text(source: bytes, node: Any) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", "ignore").strip()


def _line(node: Any) -> int:
    point = node.start_point
    try:
        row = point[0]
    except TypeError:
        row = point.row
    return int(row) + 1
