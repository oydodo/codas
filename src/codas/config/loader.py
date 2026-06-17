from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigLoadError(RuntimeError):
    """Raised when Codas configuration cannot be loaded."""


@dataclass(frozen=True)
class CodasConfig:
    path: Path
    raw: dict[str, Any]
    authoritative_sources: tuple[str, ...] = ()
    supporting_sources: tuple[str, ...] = ()
    workflow_adapter: str | None = None
    workflow_root: str | None = None
    workflow_task_globs: tuple[str, ...] = ()
    dogfooding_protocol: str | None = None
    line_index: dict[str, int] = field(default_factory=dict)


def load_codas_config(path: Path) -> CodasConfig:
    raw = load_yaml_mapping(path)
    constraint_sources = _mapping(raw.get("constraint_sources"))
    workflow = _mapping(raw.get("workflow"))
    dogfooding = _mapping(raw.get("dogfooding"))

    authoritative = _string_list(constraint_sources.get("authoritative"))
    supporting = _string_list(constraint_sources.get("supporting"))
    task_globs = _string_list(workflow.get("task_globs"))

    return CodasConfig(
        path=path,
        raw=raw,
        authoritative_sources=tuple(authoritative),
        supporting_sources=tuple(supporting),
        workflow_adapter=_optional_str(workflow.get("adapter")),
        workflow_root=_optional_str(workflow.get("root")),
        workflow_task_globs=tuple(task_globs),
        dogfooding_protocol=_optional_str(dogfooding.get("protocol")),
        line_index=index_yaml_list_lines(path),
    )


def load_waivers(path: Path) -> dict[str, Any]:
    return load_yaml_mapping(path)


def load_policies(path: Path) -> dict[str, Any]:
    return load_yaml_mapping(path)


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigLoadError(f"Required config file does not exist: {path}")
    try:
        data = parse_simple_yaml(path.read_text())
    except Exception as error:
        raise ConfigLoadError(f"Failed to parse {path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigLoadError(f"Expected YAML mapping in {path}")
    return data


def parse_simple_yaml(text: str) -> Any:
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    if not lines:
        return {}
    node, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError(f"unexpected trailing content at line {index + 1}")
    return node


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, current_text = lines[index]
    if current_indent != indent:
        raise ValueError(f"unexpected indentation at parsed line {index + 1}")
    if current_text.startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_dict(lines, index, indent)


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or not text.startswith("- "):
            break
        value = text[2:].strip()
        index += 1
        if not value:
            if index < len(lines) and lines[index][0] > indent:
                child, index = _parse_block(lines, index, lines[index][0])
                result.append(child)
            else:
                result.append(None)
        elif _looks_like_inline_mapping(value):
            result.append(_parse_inline_mapping(value))
        else:
            result.append(_parse_scalar(value))
    return result, index


def _parse_dict(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent:
            break
        if text.startswith("- "):
            break
        if ":" not in text:
            raise ValueError(f"expected key/value mapping at parsed line {index + 1}")
        key, raw_value = text.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        index += 1
        if raw_value:
            result[key] = _parse_scalar(raw_value)
        elif index < len(lines) and lines[index][0] > indent:
            child, index = _parse_block(lines, index, lines[index][0])
            result[key] = child
        else:
            result[key] = {}
    return result, index


def _looks_like_inline_mapping(value: str) -> bool:
    return ":" in value and not value.startswith(("'", '"'))


def _parse_inline_mapping(value: str) -> dict[str, Any]:
    key, raw_value = value.split(":", 1)
    return {key.strip(): _parse_scalar(raw_value.strip())}


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _optional_str(value: Any) -> str | None:
    if value is None or isinstance(value, dict):
        return None
    return str(value)


def index_yaml_list_lines(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    result: dict[str, int] = {}
    for index, raw in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("- "):
            result.setdefault(stripped[2:].strip(), index)
    return result
