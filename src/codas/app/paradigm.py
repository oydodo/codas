from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from codas.config.loader import ConfigLoadError, load_yaml_mapping

# Built-in presets ship as committed YAML data beside the package (src/codas/presets/),
# included in the wheel via [tool.setuptools.package-data] (codas = ["presets/*.yml"]).
# Resolved relative to this module so it works both under PYTHONPATH=src and pip-installed.
BUILTIN_DIR = Path(__file__).resolve().parent.parent / "presets"

# An obviously-fake, collision-proof placeholder the user renames to a real context (S4).
EXAMPLE_CONTEXT = "example_context"
_PLACEHOLDER_ROOT = "src"

_VALID_TOP_LEVEL = ("layers", "contexts")

# Ecosystem detection (R5): marker file(s) -> ecosystem tag. Cheap, deterministic, and
# MARKER-ONLY: a stray helper .py in a Node/Go repo must NOT flip it to "python" and present
# the preset as enforced (false confidence is worse than nothing). A preset whose
# enforceable_for misses every detected ecosystem renders ADVISORY (the gate's import
# resolver is Python-only, so claiming enforcement elsewhere would be dishonest).
_ECOSYSTEM_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("python", ("pyproject.toml", "setup.py", "setup.cfg")),
    ("node", ("package.json",)),
    ("go", ("go.mod",)),
    ("rust", ("Cargo.toml",)),
    ("java", ("pom.xml", "build.gradle")),
    ("ruby", ("Gemfile",)),
)


class PresetError(RuntimeError):
    """Raised when a paradigm preset is unknown, malformed or fails validation."""


@dataclass(frozen=True)
class LayerRole:
    """One layer role within a paradigm: an id plus its inward forbidden edges + prose.

    Named ``LayerRole`` (not ``Role``) to stay self-scoping against the separate
    ``src/codas/roles`` ownership-role-contracts subsystem.
    """

    id: str
    must_not_depend_on: tuple[str, ...]
    purpose: str
    canonical_placement: str


@dataclass(frozen=True)
class Preset:
    """A curated paradigm: nested layer roles + inward dependency edges + ecosystem tag.

    Pure data (no paths, no domain names, no LLM); rendered into structure.yml by
    ``render_paradigm``. ``source`` is "local" (repo ``.codas/presets/``) or "builtin".
    A preset's identity is its filename stem, which the loader requires to equal ``name``.
    """

    name: str
    description: str
    enforceable_for: tuple[str, ...]
    top_level: str  # "layers" | "contexts"
    roles: tuple[LayerRole, ...]
    source: str
    path: Path


@dataclass(frozen=True)
class RenderedParadigm:
    """The structure.yml fragment a preset renders to: planned units + dep rules + prose."""

    units: dict[str, dict[str, str]]
    dependency_rules: dict[str, dict[str, list[str]]]
    prose: str  # comment header (no leading '#'), woven above the units
    advisory: bool  # the detected ecosystem has no Python resolver -> gate won't enforce


# --------------------------------------------------------------------------- loading


def load_preset(repo: Path, name: str) -> Preset:
    """Resolve a preset by name: repo ``.codas/presets/<name>.yml`` shadows the built-in.

    A user preset of the same name as a built-in wins (overridable lazy default, the eslint
    shareable-config model). Identity is the filename stem; the loader requires the file's
    declared ``name`` to match it, so ``paradigm list`` and ``--paradigm <name>`` never
    disagree. Unknown name -> ``PresetError`` listing the available presets.
    """
    local = repo / ".codas" / "presets" / f"{name}.yml"
    if local.is_file():
        return _parse_preset(local, "local")
    builtin = BUILTIN_DIR / f"{name}.yml"
    if builtin.is_file():
        return _parse_preset(builtin, "builtin")
    available = ", ".join(n for n, _, _ in list_presets(repo)) or "(none)"
    raise PresetError(f"unknown paradigm preset {name!r}; available: {available}")


def list_presets(repo: Path) -> list[tuple[str, str, str]]:
    """List ``(name, description, source)`` for repo-local + built-in presets, name-sorted.

    A local preset shadows a built-in of the same name. ``name`` equals the filename stem
    (enforced at load), so every listed name is exactly what ``--paradigm`` accepts. Malformed
    local files are skipped so listing never crashes; built-ins are committed and must parse.
    """
    seen: dict[str, tuple[str, str, str]] = {}
    local_dir = repo / ".codas" / "presets"
    local_files = sorted(local_dir.glob("*.yml")) if local_dir.is_dir() else []
    for path in local_files:
        try:
            preset = _parse_preset(path, "local")
        except (PresetError, ConfigLoadError):
            continue
        seen.setdefault(preset.name, (preset.name, preset.description, "local"))
    for path in sorted(BUILTIN_DIR.glob("*.yml")):
        preset = _parse_preset(path, "builtin")
        seen.setdefault(preset.name, (preset.name, preset.description, "builtin"))
    return [seen[name] for name in sorted(seen)]


def _parse_preset(path: Path, source: str) -> Preset:
    try:
        raw = load_yaml_mapping(path)
    except ConfigLoadError as error:
        raise PresetError(str(error)) from error

    name = _require_str(raw, "name", path)
    if name != path.stem:
        raise PresetError(
            f"preset {path.name}: declared name {name!r} must match the filename stem "
            f"{path.stem!r} (identity is the filename)"
        )
    description = _require_str(raw, "description", path)
    top_level = _require_str(raw, "top_level", path)
    if top_level not in _VALID_TOP_LEVEL:
        raise PresetError(
            f"preset {path.name}: top_level must be one of {_VALID_TOP_LEVEL}, got {top_level!r}"
        )
    enforceable_for = _require_str_list(raw.get("enforceable_for"), "enforceable_for", path)
    if not enforceable_for:
        raise PresetError(f"preset {path.name}: enforceable_for must be a non-empty list")

    # The role list lives under `layers` for a contexts preset, `roles` for a layers preset.
    # Strict (no cross-fallback) so a mis-keyed user preset fails loudly before any write.
    roles_key = "layers" if top_level == "contexts" else "roles"
    roles_raw = raw.get(roles_key)
    if not isinstance(roles_raw, list) or not roles_raw:
        raise PresetError(
            f"preset {path.name}: a {top_level!r} preset needs a non-empty {roles_key!r} list"
        )

    roles = _parse_roles(roles_raw, path)

    return Preset(
        name=name,
        description=description,
        enforceable_for=tuple(enforceable_for),
        top_level=top_level,
        roles=roles,
        source=source,
        path=path,
    )


def _parse_roles(roles_raw: list[Any], path: Path) -> tuple[LayerRole, ...]:
    roles: list[LayerRole] = []
    ids: list[str] = []
    for entry in roles_raw:
        if not isinstance(entry, dict):
            raise PresetError(f"preset {path.name}: each role must be a mapping")
        role_id = _require_str(entry, "id", path)
        if role_id in ids:
            raise PresetError(f"preset {path.name}: duplicate role id {role_id!r}")
        ids.append(role_id)
        roles.append(
            LayerRole(
                id=role_id,
                # Strict: a scalar typo (`must_not_depend_on: adapters`) must raise, not
                # silently coerce to [] and drop the edge (lost enforcement).
                must_not_depend_on=tuple(
                    _require_str_list(
                        entry.get("must_not_depend_on"), "must_not_depend_on", path
                    )
                ),
                purpose=_require_str(entry, "purpose", path),
                canonical_placement=_require_str(entry, "canonical_placement", path),
            )
        )
    sibling_ids = set(ids)
    for role in roles:
        for target in role.must_not_depend_on:
            if target not in sibling_ids:
                raise PresetError(
                    f"preset {path.name}: role {role.id!r} must_not_depend_on references "
                    f"unknown role {target!r}"
                )
            if target == role.id:
                raise PresetError(
                    f"preset {path.name}: role {role.id!r} must_not_depend_on lists itself"
                )
    return tuple(roles)


def _require_str(body: dict[str, Any], field: str, path: Path) -> str:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PresetError(f"preset {path.name}: missing required string field {field!r}")
    return value


def _require_str_list(value: Any, field: str, path: Path) -> list[str]:
    """A list of non-empty strings. ``None`` -> ``[]``; any other shape is a hard error.

    Catches the silent-coercion trap: a scalar where a list is expected must raise (so a
    malformed user preset fails atomically before init writes), never drop to an empty list.
    """
    if value is None:
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise PresetError(
            f"preset {path.name}: {field!r} must be a list of non-empty strings"
        )
    return [str(item) for item in value]


# --------------------------------------------------------------------- ecosystem (R5)


def detect_ecosystems(repo: Path) -> set[str]:
    """Detect the repo's ecosystems from cheap, deterministic packaging marker files.

    Marker-only (e.g. python <- pyproject.toml/setup.py/setup.cfg): used to decide whether a
    preset can be ENFORCED (Python resolver) or must render advisory. Deliberately does NOT
    treat an incidental ``*.py`` as "python" — a stray script in a Node/Go repo must not flip
    the preset to enforced. Never sniffs a paradigm — only the language.
    """
    found: set[str] = set()
    for tag, markers in _ECOSYSTEM_MARKERS:
        if any((repo / marker).exists() for marker in markers):
            found.add(tag)
    return found


def is_advisory(preset: Preset, ecosystems: set[str]) -> bool:
    """A preset is advisory when no detected ecosystem is one its gate can enforce."""
    return not (set(preset.enforceable_for) & ecosystems)


# ------------------------------------------------------------------- render (R3/R4)


def render_paradigm(
    preset: Preset, *, context: str = EXAMPLE_CONTEXT, advisory: bool = False
) -> RenderedParadigm:
    """Render a preset into one example context's nested layer units + dep rules + prose.

    Each role -> a unit ``{context}-{role.id}`` at placeholder path ``src/{context}/{role.id}``,
    ``status: planned``. A fresh ``codas check`` is GREEN for two INDEPENDENT reasons:
    structure_drift exempts planned units, AND the placeholder path owns no real files so
    dependency_direction has nothing to resolve. NB dependency_direction does NOT consult
    status — a rule arms the moment its unit's path maps to real files (the S4 step), not when
    status flips. Deterministic: roles emit in preset list order; rendering twice is byte-equal.
    """
    units: dict[str, dict[str, str]] = {}
    rules: dict[str, dict[str, list[str]]] = {}
    advisory_note = (
        " ADVISORY: codas's dependency gate does not enforce this paradigm here."
        if advisory
        else ""
    )
    for role in preset.roles:
        uid = f"{context}-{role.id}"
        units[uid] = {
            "path": f"{_PLACEHOLDER_ROOT}/{context}/{role.id}",
            "kind": "layer",
            "owner": "maintainers",
            "purpose": role.purpose,
            "canonical_placement": role.canonical_placement + advisory_note,
            "status": "planned",
        }
        if role.must_not_depend_on:
            rules[uid] = {
                "must_not_depend_on": [f"{context}-{t}" for t in role.must_not_depend_on]
            }
    return RenderedParadigm(
        units=units,
        dependency_rules=rules,
        prose=_prose(preset, context, advisory),
        advisory=advisory,
    )


def _prose(preset: Preset, context: str, advisory: bool) -> str:
    lines = [
        f"Paradigm: {preset.name} — {preset.description}",
        "",
        f"This is a context STAMP: one example context ({context!r}) with its layers nested",
        "inside. Rename it to a real context and map each layer unit's `path` to a real",
        "directory — mapping the path is what ARMS its dependency rules: dependency_direction",
        "enforces as soon as the path owns real files (it does not consult status). Flip",
        "`status: planned` -> `active` to keep structure_drift satisfied once the path is real.",
    ]
    if preset.top_level == "contexts":
        lines.append(
            "Replicate this stamp under each bounded context; cross-context isolation becomes"
        )
        lines.append(
            "a gate once you declare published interfaces (epic sub-task S5)."
        )
    lines += [
        "Until a path owns real files the rules are inert and `codas check` is GREEN.",
    ]
    if advisory:
        lines += [
            "",
            "ADVISORY: this repo's ecosystem has no Python import resolver, so codas's",
            "dependency_direction gate will NOT enforce these rules. They document intent only.",
        ]
    return "\n".join(lines)


def render_structure_yaml(rendered: RenderedParadigm) -> str:
    """Serialize a rendered paradigm into a complete, deterministic structure.yml string.

    Keeps the root catch-all unit (so missing_structure_owner stays inert) and appends the
    planned layer units + dependency_rules. The prose renders as a leading comment block.
    Determinism is pinned in-repo, not inherited from PyYAML defaults: fixed key order
    (sort_keys=False), fixed role order, and an explicit ``width`` so long canonical_placement
    strings are not implicitly line-folded (so repeated ``init --force`` is byte-stable).
    """
    units: dict[str, dict[str, str]] = {
        "root": {
            "path": ".",
            "kind": "directory",
            "owner": "maintainers",
            "purpose": "Repository root.",
            "canonical_placement": "Top-level files belong at the repository root.",
        },
    }
    units.update(rendered.units)
    document: dict[str, Any] = {
        "version": 1,
        "kind": "structure_map",
        "source": ".codas/structure.yml",
        "units": units,
    }
    if rendered.dependency_rules:
        document["dependency_rules"] = rendered.dependency_rules
    body = yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=4096,  # pin folding: don't inherit PyYAML's 80-col default
    )
    header = "".join(f"# {line}\n".rstrip() + "\n" for line in rendered.prose.splitlines())
    return header + body
