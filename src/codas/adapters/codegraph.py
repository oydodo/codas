from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodeGraphCallFact:
    caller_module: str
    caller_class: str
    caller_symbol: str
    caller_path: str
    caller_line: int
    callee_module: str
    callee_class: str
    callee_symbol: str
    callee_path: str
    callee_line: int
    resolution: str
    provenance: str = "codegraph"


@dataclass(frozen=True)
class CodeGraphCallFacts:
    edges: tuple[CodeGraphCallFact, ...]
    skipped: tuple[str, ...]


def extract_codegraph_calls(
    repo: Path,
    files: tuple[str, ...],
    executable: str | os.PathLike[str] | None = None,
    timeout: float = 15.0,
) -> CodeGraphCallFacts:
    """Run optional CodeGraph and normalize advisory call edges.

    CodeGraph is an external CLI, not a Python dependency. Missing binaries, invalid
    output and non-zero exits are advisory absence, never scan failures.
    """
    command = _command(repo, executable)
    try:
        result = subprocess.run(
            command,
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return CodeGraphCallFacts(edges=(), skipped=("codegraph: executable not found",))
    except subprocess.TimeoutExpired:
        return CodeGraphCallFacts(edges=(), skipped=("codegraph: timeout",))
    except OSError as error:
        return CodeGraphCallFacts(edges=(), skipped=(f"codegraph: {error.__class__.__name__}",))

    if result.returncode != 0:
        return CodeGraphCallFacts(edges=(), skipped=(f"codegraph: exit {result.returncode}",))
    return parse_codegraph_calls(result.stdout, repo, files)


def parse_codegraph_calls(payload: str, repo: Path, files: tuple[str, ...]) -> CodeGraphCallFacts:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        return CodeGraphCallFacts(edges=(), skipped=("codegraph: invalid-json",))

    rows = _edge_rows(raw)
    if rows is None:
        return CodeGraphCallFacts(edges=(), skipped=("codegraph: unsupported-schema",))

    known_files = set(files)
    edges: list[CodeGraphCallFact] = []
    skipped: list[str] = []
    seen: set[tuple[str, str, str, str, str, str, str]] = set()

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped.append(f"edge[{index}]: not-object")
            continue
        fact, reason = _parse_edge(row, index, repo, known_files)
        if reason is not None:
            skipped.append(reason)
            continue
        assert fact is not None
        key = (
            fact.caller_path,
            fact.caller_class,
            fact.caller_symbol,
            fact.callee_path,
            fact.callee_class,
            fact.callee_symbol,
            fact.resolution,
        )
        if key in seen:
            continue
        seen.add(key)
        edges.append(fact)

    edges.sort(
        key=lambda edge: (
            edge.caller_path,
            edge.caller_class,
            edge.caller_symbol,
            edge.callee_path,
            edge.callee_class,
            edge.callee_symbol,
            edge.resolution,
            edge.provenance,
        )
    )
    return CodeGraphCallFacts(edges=tuple(edges), skipped=tuple(sorted(skipped)))


def _command(repo: Path, executable: str | os.PathLike[str] | None) -> list[str]:
    raw = str(executable or os.environ.get("CODAS_CODEGRAPH") or "codegraph")
    parts = shlex.split(raw)
    if not parts:
        parts = ["codegraph"]
    return [*parts, repo.as_posix()]


def _edge_rows(raw: Any) -> list[Any] | None:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return None
    for key in ("edges", "calls", "callEdges", "links"):
        value = raw.get(key)
        if isinstance(value, list):
            return value
    graph = raw.get("graph")
    if isinstance(graph, dict):
        value = graph.get("edges")
        if isinstance(value, list):
            return value
    return None


def _parse_edge(
    row: dict[str, Any],
    index: int,
    repo: Path,
    known_files: set[str],
) -> tuple[CodeGraphCallFact | None, str | None]:
    caller, reason = _endpoint(row, "caller", repo, known_files)
    if reason is not None:
        return None, f"edge[{index}]: caller {reason}"
    callee, reason = _endpoint(row, "callee", repo, known_files)
    if reason is not None:
        return None, f"edge[{index}]: callee {reason}"
    assert caller is not None and callee is not None

    resolution = _string(row, ("resolution", "resolution_tag", "resolutionTag", "kind", "type"))
    if not resolution:
        resolution = "heuristic"

    return (
        CodeGraphCallFact(
            caller_module=caller["module"],
            caller_class=caller["class"],
            caller_symbol=caller["symbol"],
            caller_path=caller["path"],
            caller_line=caller["line"],
            callee_module=callee["module"],
            callee_class=callee["class"],
            callee_symbol=callee["symbol"],
            callee_path=callee["path"],
            callee_line=callee["line"],
            resolution=resolution,
        ),
        None,
    )


def _endpoint(
    row: dict[str, Any],
    role: str,
    repo: Path,
    known_files: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    nested = row.get(role)
    if not isinstance(nested, dict):
        nested = {}
    prefix = role + "_"
    camel = role

    path = _string(
        nested,
        ("path", "file", "file_path", "filePath", "filename", "uri"),
    ) or _string(
        row,
        (
            prefix + "path",
            prefix + "file",
            prefix + "file_path",
            camel + "Path",
            camel + "File",
        ),
    )
    if not path:
        return None, "missing-path"
    rel_path = _repo_rel(path, repo)
    if rel_path is None or (known_files and rel_path not in known_files and _outside_repo(path, repo)):
        return None, "outside-repo"

    symbol = _string(
        nested,
        ("symbol", "name", "function", "method", "label"),
    ) or _string(
        row,
        (
            prefix + "symbol",
            prefix + "name",
            prefix + "function",
            prefix + "method",
            camel + "Symbol",
            camel + "Name",
        ),
    )
    if not symbol:
        return None, "missing-symbol"

    module = _string(nested, ("module", "module_name", "moduleName")) or _string(
        row, (prefix + "module", prefix + "module_name", camel + "Module")
    )
    cls = _string(nested, ("class", "cls", "class_name", "className")) or _string(
        row, (prefix + "class", prefix + "cls", prefix + "class_name", camel + "Class")
    )
    line = _int(
        _value(nested, ("line", "line_number", "lineNumber", "startLine"))
        or _value(row, (prefix + "line", prefix + "line_number", camel + "Line"))
    )
    return (
        {
            "module": module or _module_from_path(rel_path),
            "class": cls or "",
            "symbol": symbol,
            "path": rel_path,
            "line": line,
        },
        None,
    )


def _value(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _string(mapping: dict[str, Any], keys: tuple[str, ...]) -> str:
    value = _value(mapping, keys)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _int(value: Any) -> int:
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, str):
        try:
            return max(int(value), 0)
        except ValueError:
            return 0
    return 0


def _repo_rel(raw: str, repo: Path) -> str | None:
    value = raw.removeprefix("file://").replace("\\", "/")
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return None
    while value.startswith("./"):
        value = value[2:]
    if value == ".." or value.startswith("../") or not value:
        return None
    return value


def _outside_repo(raw: str, repo: Path) -> bool:
    value = raw.removeprefix("file://")
    path = Path(value)
    if not path.is_absolute():
        return False
    try:
        path.resolve().relative_to(repo.resolve())
    except ValueError:
        return True
    return False


def _module_from_path(path: str) -> str:
    no_suffix = path.rsplit(".", 1)[0]
    return no_suffix.replace("/", ".")
