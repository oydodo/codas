from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys.

    Authored governance claim surfaces must not silently last-write-wins a
    duplicated unit, source or rule; that would drop a claim without warning.
    """

    def construct_mapping(self, node, deep=False):  # type: ignore[override]
        seen: set[object] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep)


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
    """Load a YAML file that must contain a top-level mapping.

    Uses PyYAML's safe loader; Codas authored claim surfaces (config, policies,
    waivers, structure map, program plan) are all top-level mappings.
    """
    if not path.exists():
        raise ConfigLoadError(f"Required config file does not exist: {path}")
    try:
        data = yaml.load(path.read_text(), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise ConfigLoadError(f"Failed to parse {path}: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigLoadError(f"Expected YAML mapping in {path}")
    return data


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
    """Map list-item scalars to their 1-based line number for evidence anchors.

    A lightweight, regex-free scan independent of the YAML parser; used to
    attach source line numbers to findings about authoritative source globs.
    """
    if not path.exists():
        return {}
    result: dict[str, int] = {}
    for index, raw in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if (item.startswith('"') and item.endswith('"')) or (
                item.startswith("'") and item.endswith("'")
            ):
                item = item[1:-1]
            result.setdefault(item, index)
    return result
