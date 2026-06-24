from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codas.adapters.python import ImportFacts, SymbolFacts
from codas.adapters.swift import extract_swift_imports, extract_swift_symbols
from codas.adapters.swift_parse import parse_swift_modules, parse_swift_sources


@dataclass(frozen=True)
class LanguageExtractor:
    name: str
    extensions: tuple[str, ...]


LANGUAGES = (
    LanguageExtractor(name="swift", extensions=(".swift",)),
)

LANGUAGE_EXTENSIONS = tuple(
    extension
    for language in LANGUAGES
    for extension in language.extensions
)


def extract_language_symbols(repo: Path, files: tuple[str, ...]) -> SymbolFacts:
    parsed = parse_swift_modules(repo, files)
    return extract_swift_symbols(parsed)


def extract_language_imports(repo: Path, files: tuple[str, ...]) -> ImportFacts:
    parsed = parse_swift_modules(repo, files)
    return extract_swift_imports(parsed)


def extract_language_symbols_from_sources(sources: dict[str, str | bytes]) -> SymbolFacts:
    parsed = parse_swift_sources(sources)
    return extract_swift_symbols(parsed)


def extract_language_imports_from_sources(sources: dict[str, str | bytes]) -> ImportFacts:
    parsed = parse_swift_sources(sources)
    return extract_swift_imports(parsed)
