from __future__ import annotations

import re
from pathlib import Path

from codas.config.loader import CodasConfig
from codas.core.models import Evidence, Finding


def check_dogfooding_protocol(repo: Path, config: CodasConfig) -> list[Finding]:
    protocol = config.dogfooding_protocol
    if not protocol:
        return [
            Finding(
                severity="warning",
                check_id="dogfooding-protocol-missing",
                message="Dogfooding is enabled but no protocol path is configured.",
                evidence=[Evidence(path=_rel(repo, config.path))],
                recommendation="Set dogfooding.protocol in .codas/config.yml.",
            )
        ]

    rel_path, fragment = _split_fragment(protocol)
    path = repo / rel_path
    if not path.exists():
        return [
            Finding(
                severity="error",
                check_id="dogfooding-protocol-target-missing",
                message=f"Dogfooding protocol target does not exist: {protocol}",
                evidence=[
                    Evidence(
                        path=_rel(repo, config.path),
                        line=config.line_index.get(protocol),
                        detail=protocol,
                    )
                ],
                recommendation="Update dogfooding.protocol or add the target document.",
            )
        ]

    if fragment and not _html_fragment_exists(path, fragment):
        return [
            Finding(
                severity="error",
                check_id="dogfooding-protocol-fragment-missing",
                message=f"Dogfooding protocol fragment does not exist: #{fragment}",
                evidence=[
                    Evidence(
                        path=_rel(repo, config.path),
                        line=config.line_index.get(protocol),
                        detail=protocol,
                    ),
                    Evidence(path=_rel(repo, path)),
                ],
                recommendation="Add the HTML id or update dogfooding.protocol.",
                meta={"fragment": fragment},
            )
        ]
    return []


def _split_fragment(value: str) -> tuple[str, str | None]:
    if "#" not in value:
        return value, None
    path, fragment = value.split("#", 1)
    return path, fragment or None


def _html_fragment_exists(path: Path, fragment: str) -> bool:
    text = path.read_text(errors="ignore")
    escaped = re.escape(fragment)
    return bool(re.search(rf"\bid\s*=\s*['\"]{escaped}['\"]", text))


def _rel(repo: Path, path: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()
