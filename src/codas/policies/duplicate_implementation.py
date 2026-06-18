from __future__ import annotations

from collections import defaultdict

from codas.config.loader import ConfigLoadError, load_claims
from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext, SymbolFact

CLAIMS_SOURCE = ".codas/claims.yml"
SCOPE_PREFIX = "src/"
VALID_RELATIONSHIPS = frozenset({"canonical", "variant", "migration"})


def check_duplicate_implementation(ctx: ScanContext) -> list[Finding]:
    """Flag top-level symbols implemented in 2+ src modules without a declared claim.

    Schema §8 / plan §10 ``duplicate_implementation``: "Repeated symbols ... require
    canonical, variant or migration claims" / "Error when a second implementation
    lacks a declared relationship." Detection covers public AND private top-level
    symbols under ``src/`` (a duplicate is a duplicate regardless of visibility);
    a symbol named in a valid ``.codas/claims.yml`` ``duplicate_relationships``
    entry is suppressed. Deterministic, no LLM (§17). Supersedes the warning-only
    ``duplicate_symbol`` first cut now that a claim suppression surface exists.

    Symbol facts come from the `ScanContext` (plan §11 Adapter Boundary) — the
    policy imports no adapter. Claim loading stays policy-local: claims are
    governance input, not a scanned fact, so the facts provider never absorbs it.
    """
    claims_path = ctx.repo / ".codas" / "claims.yml"
    claimed: dict[str, set[frozenset[str]]] = {}
    findings: list[Finding] = []

    if claims_path.exists():
        try:
            claims_doc = load_claims(claims_path)
        except ConfigLoadError as error:
            return [
                Finding(
                    severity="error",
                    check_id="claims-load-error",
                    message=str(error),
                    evidence=[Evidence(path=CLAIMS_SOURCE)],
                )
            ]
        schema_findings, claimed = _read_relationships(claims_doc)
        findings.extend(schema_findings)

    facts = ctx.symbols()

    by_name: dict[str, list[SymbolFact]] = defaultdict(list)
    for definition in facts.definitions:
        if definition.module.startswith(SCOPE_PREFIX):
            by_name[definition.name].append(definition)

    duplicates: list[Finding] = []
    for name in sorted(by_name):
        occurrences = by_name[name]
        modules = sorted({occ.module for occ in occurrences})
        if len(modules) < 2:
            continue
        # A claim suppresses only the EXACT module set it covers, so a future
        # same-name duplicate in different modules is not silently suppressed.
        if frozenset(modules) in claimed.get(name, set()):
            continue
        evidence = [
            Evidence(path=occ.module, line=occ.line, detail=occ.kind)
            for occ in sorted(occurrences, key=lambda occ: (occ.module, occ.line))
        ]
        duplicates.append(
            Finding(
                severity="error",
                check_id="duplicate-implementation",
                message=(
                    f"Symbol '{name}' is implemented in {len(modules)} modules "
                    f"without a declared relationship: {', '.join(modules)}"
                ),
                evidence=evidence,
                recommendation=(
                    "Consolidate into one definition, or declare a "
                    "canonical/variant/migration relationship in .codas/claims.yml."
                ),
                meta={"name": name, "modules": modules},
            )
        )

    duplicates.sort(key=lambda finding: finding.meta["name"])
    return findings + duplicates


def _read_relationships(
    claims_doc: dict,
) -> tuple[list[Finding], dict[str, set[frozenset[str]]]]:
    """Validate duplicate_relationships → (schema findings, claimed name→module-sets).

    Only a fully valid entry contributes to ``claimed`` (a malformed entry must not
    silently suppress a duplicate). Each claim covers the EXACT module set it lists.
    """
    relationships = claims_doc.get("duplicate_relationships", [])
    if not isinstance(relationships, list):
        return (
            [
                Finding(
                    severity="error",
                    check_id="claim-schema-invalid",
                    message="duplicate_relationships must be a list.",
                    evidence=[Evidence(path=CLAIMS_SOURCE)],
                    recommendation="Fix .codas/claims.yml.",
                )
            ],
            {},
        )

    findings: list[Finding] = []
    claimed: dict[str, set[frozenset[str]]] = defaultdict(set)
    for index, entry in enumerate(relationships, start=1):
        problem = _entry_problem(entry)
        if problem is not None:
            findings.append(_schema_invalid(index, problem))
            continue
        claimed[entry["symbol"]].add(frozenset(entry["modules"]))
    return findings, claimed


def _entry_problem(entry: object) -> str | None:
    """Return the first schema problem with a relationship entry, or None if valid."""
    if not isinstance(entry, dict):
        return "relationship entry must be a mapping"
    missing = [key for key in ("symbol", "owner", "reason") if not entry.get(key)]
    if missing:
        return f"relationship is missing {', '.join(missing)}"
    if entry.get("relationship") not in VALID_RELATIONSHIPS:
        return f"relationship must be one of {sorted(VALID_RELATIONSHIPS)}"
    modules = entry.get("modules")
    if not isinstance(modules, list) or not modules or not all(
        isinstance(module, str) and module for module in modules
    ):
        return "modules must be a non-empty list of paths"
    return None


def _schema_invalid(index: int, message: str) -> Finding:
    return Finding(
        severity="error",
        check_id="claim-schema-invalid",
        message=message,
        evidence=[Evidence(path=CLAIMS_SOURCE, detail=f"duplicate_relationships[{index}]")],
        recommendation="Fix .codas/claims.yml or remove the invalid relationship.",
    )
