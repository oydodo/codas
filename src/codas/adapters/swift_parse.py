from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParsedSwiftModule:
    path: str
    tree: Any | None
    source: bytes
    read_error: OSError | None = None


@dataclass(frozen=True)
class ParsedSwiftModules:
    modules: tuple[ParsedSwiftModule, ...]
    unavailable: str | None = None


_UNAVAILABLE_NOTICE_EMITTED = False


def parse_swift_modules(repo: Path, files: tuple[str, ...]) -> ParsedSwiftModules:
    """Read and parse scanned ``.swift`` files with tree-sitter, if installed."""
    sources: dict[str, bytes] = {}
    read_errors: list[ParsedSwiftModule] = []
    for rel in sorted(f for f in files if f.endswith(".swift")):
        try:
            sources[rel] = (repo / rel).read_bytes()
        except OSError as exc:
            read_errors.append(ParsedSwiftModule(path=rel, tree=None, source=b"", read_error=exc))
    parsed = parse_swift_sources(sources)
    if not read_errors:
        return parsed
    modules = tuple(sorted((*parsed.modules, *read_errors), key=lambda module: module.path))
    return ParsedSwiftModules(modules=modules, unavailable=parsed.unavailable)


def parse_swift_sources(sources: dict[str, str | bytes]) -> ParsedSwiftModules:
    """Parse already-read Swift source keyed by repo-relative path."""
    swift_sources = {
        path: _to_bytes(source)
        for path, source in sources.items()
        if path.endswith(".swift")
    }
    if not swift_sources:
        return ParsedSwiftModules(())

    parser, unavailable = _swift_parser()
    if parser is None:
        _emit_unavailable_notice(unavailable)
        return ParsedSwiftModules(
            modules=tuple(
                ParsedSwiftModule(path=path, tree=None, source=swift_sources[path])
                for path in sorted(swift_sources)
            ),
            unavailable=unavailable,
        )

    modules: list[ParsedSwiftModule] = []
    for path in sorted(swift_sources):
        source = swift_sources[path]
        try:
            tree = parser.parse(source)
        except Exception:  # tree-sitter parser errors are environment/ABI failures.
            modules.append(ParsedSwiftModule(path=path, tree=None, source=source))
            continue
        if tree.root_node.has_error:
            modules.append(ParsedSwiftModule(path=path, tree=None, source=source))
        else:
            modules.append(ParsedSwiftModule(path=path, tree=tree, source=source))
    return ParsedSwiftModules(tuple(modules))


def _swift_parser() -> tuple[Any | None, str | None]:
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_swift

        language = Language(tree_sitter_swift.language())
        try:
            return Parser(language), None
        except TypeError:
            parser = Parser()
            if hasattr(parser, "set_language"):
                parser.set_language(language)
            else:
                parser.language = language
            return parser, None
    except Exception as exc:
        return None, str(exc)


def _to_bytes(source: str | bytes) -> bytes:
    if isinstance(source, bytes):
        return source
    return source.encode("utf-8", "ignore")


def _emit_unavailable_notice(reason: str | None) -> None:
    global _UNAVAILABLE_NOTICE_EMITTED
    if _UNAVAILABLE_NOTICE_EMITTED:
        return
    suffix = f": {reason}" if reason else ""
    sys.stderr.write(
        "codas: Swift extraction unavailable; install codas[swift] on Python >=3.10"
        f"{suffix}\n"
    )
    _UNAVAILABLE_NOTICE_EMITTED = True
