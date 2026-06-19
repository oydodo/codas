from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedModule:
    """One read+``ast.parse`` attempt of a repo-relative ``.py`` file.

    Three states, so each extractor can reproduce its OWN historical error policy
    byte-for-byte from one shared read:

    - success: ``tree`` set, ``read_error`` ``None``;
    - parse failure (``SyntaxError | ValueError``): ``tree`` ``None``, ``read_error``
      ``None``;
    - read failure (``OSError``): ``tree`` ``None``, ``read_error`` the exception.

    The read-vs-parse distinction matters because the legacy extractors diverged on
    it: ``symbols``/``imports`` caught ``OSError`` (→ skipped), while ``callgraph``
    caught only ``SyntaxError``/``ValueError`` and let an ``OSError`` propagate. The
    call extractor re-raises ``read_error`` to preserve that exact crash-vs-skip
    semantics; ``symbols``/``imports`` treat any ``tree is None`` as skipped.
    """

    path: str
    tree: ast.Module | None
    read_error: OSError | None = None


@dataclass(frozen=True)
class ParsedModules:
    """The single per-run parse pass over the scanned ``.py`` files.

    ``modules`` is ordered by repo-relative path so every downstream extractor
    iterates a stable order. One ``ast.parse`` per file per run — the symbol, import
    and call extractors consume this instead of each re-reading and re-parsing every
    file (previously 3× parse per file). Pure, deterministic, no cross-file
    resolution (that stays in the individual extractors, which own their vocabulary).
    """

    modules: tuple[ParsedModule, ...]


def parse_python_modules(repo: Path, files: tuple[str, ...]) -> ParsedModules:
    """Read + ``ast.parse`` each scanned ``.py`` file exactly once.

    Reads with ``errors="ignore"`` (matching the legacy extractors) and records the
    outcome per file without raising here, so a stray unreadable/unparseable file
    never hard-fails the shared scan. Read and parse failures are recorded as
    DISTINCT states (``read_error`` vs a plain ``None`` tree) so each extractor
    reproduces its own historical skip/propagate policy byte-for-byte. No package,
    scope or resolution logic lives here — the extractors know their own rules.

    NB this reads EVERY scanned ``.py`` (including files the call extractor will later
    treat as out-of-scope). That is not new exposure: ``symbols``/``imports`` already
    read every ``.py`` in any run, so the unified scan's read surface equals the
    legacy ``symbols``/``imports`` surface; only a standalone ``extract_call_facts``
    call reads more than its legacy self did (it excluded non-package files before
    reading) — harmless, since out-of-scope reads are dropped before resolution.
    """
    out: list[ParsedModule] = []
    for rel in sorted(f for f in files if f.endswith(".py")):
        try:
            source = (repo / rel).read_text(errors="ignore")
        except OSError as exc:  # legacy: symbols/imports skip; callgraph propagates
            out.append(ParsedModule(path=rel, tree=None, read_error=exc))
            continue
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            out.append(ParsedModule(path=rel, tree=None))
            continue
        out.append(ParsedModule(path=rel, tree=tree))
    return ParsedModules(tuple(out))
