from __future__ import annotations

import fnmatch

from codas.config.loader import ConfigLoadError, load_claims
from codas.core.models import Evidence, Finding
from codas.facts.context import ScanContext

CLAIMS_SOURCE = ".codas/claims.yml"


def check_spec_drift(ctx: ScanContext) -> list[Finding]:
    """Verify vouched drift couplings against the working-tree diff (spec_drift).

    Plan: "Changes to behavior, architecture, commands, policies or data model must
    update their authoritative claim source." The Structure Map's
    ``must_update_if_changed`` scopes that obligation to changes that are *material*
    (schema §4) — a semantic judgment the correctness core may not make (§17). So
    Codas splits the contract: the coarse ``must_update_if_changed`` hints stay
    advisory, while the **gating** obligation is a *vouched drift coupling* — a
    co-change rule whose materiality an agent or human has judged and recorded in
    ``.codas/claims.yml`` ``drift_couplings``.

    This policy is the deterministic half of that split: Codas grounds the change
    (``ctx.changed_paths()`` — which files moved since HEAD) and verifies the coupling
    (is each required reaction present in the same diff?). The host agent supplies the
    semantic judgment by authoring the coupling; Codas never guesses materiality. The
    live repo ships with no ``drift_couplings``, so on a clean tree — and until a
    coupling is authored — this returns ``[]`` (the resting gate stays green; teeth are
    opt-in and vouched).

    A coupling::

        drift_couplings:
          - when_changed: <repo-rel path or glob>     # the change site judged material
            requires: [<repo-rel path or glob>, ...]  # reactions that must co-change
            owner: <responsible owner>
            reason: <why this co-change obligation is material>

    fires one finding per requirement that has no matching changed path, but only when
    the ``when_changed`` site itself appears in the diff. Glob-aware (``fnmatch``).
    Consumes facts via the ScanContext seam (no adapter import, §11); deterministic
    (total-key sort). Severity ``error`` (matches ``.codas/policies.yml``).
    """
    changed = ctx.changed_paths()
    if not changed:
        return []  # clean tree (or non-git) -> no diff -> no drift

    claims_path = ctx.repo / ".codas" / "claims.yml"
    if not claims_path.exists():
        return []
    try:
        claims_doc = load_claims(claims_path)
    except ConfigLoadError as error:
        # Mirror duplicate_implementation: a malformed claim surface is one error,
        # not a crash. duplicate_implementation already owns the canonical
        # claims-load-error finding, so stay silent here to avoid a duplicate finding.
        _ = error
        return []

    couplings = claims_doc.get("drift_couplings")
    if not isinstance(couplings, list):
        return []

    findings: list[Finding] = []
    for entry in couplings:
        if not isinstance(entry, dict):
            continue
        when = entry.get("when_changed")
        if not isinstance(when, str) or not _any_match(changed, when):
            continue  # change site absent from the diff -> coupling dormant
        requires = entry.get("requires")
        if not isinstance(requires, list):
            continue
        owner = entry.get("owner")
        reason = entry.get("reason")
        for requirement in requires:
            if not isinstance(requirement, str) or _any_match(changed, requirement):
                continue
            findings.append(
                Finding(
                    severity="error",
                    check_id="spec-drift",
                    message=(
                        f"Change to '{when}' requires a co-update of '{requirement}', "
                        "which is not present in this change"
                    ),
                    evidence=[
                        Evidence(
                            path=CLAIMS_SOURCE,
                            detail=f"drift_couplings[{when}] -> {requirement}",
                        )
                    ],
                    recommendation=(
                        "Update the required claim source in the same change, or revise "
                        "or justify the drift coupling in .codas/claims.yml."
                    ),
                    meta={
                        "when_changed": when,
                        "requires": requirement,
                        "owner": owner or "",
                        "reason": reason or "",
                    },
                )
            )

    findings.sort(
        key=lambda finding: (
            finding.meta["when_changed"],
            finding.meta["requires"],
            finding.message,
        )
    )
    return findings


def _any_match(paths: tuple[str, ...], pattern: str) -> bool:
    """True if any changed path equals or fnmatch-globs ``pattern``.

    Note `fnmatch` semantics: ``*`` is not slash-aware, so ``docs/policies/*.md``
    also matches ``docs/policies/sub/foo.md``. That is intentional for coupling
    patterns (a coupling names a region of the tree), but authors should write a more
    specific pattern when they mean a single directory level.
    """
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for path in paths)
