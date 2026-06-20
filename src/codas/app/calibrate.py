from __future__ import annotations

from pathlib import Path
from typing import Any

from codas.app.wiki import build_atlas_tree
from codas.config.loader import load_codas_config
from codas.facts.context import ScanContext, build_scan_context
from codas.facts.openworld import world_of

# W3·S3 — the semantic judge tier's DETERMINISTIC middle (FEED + CALIBRATE). §17: Codas runs
# NO model here. The host agent (already an LLM) generates the corpus prose; this module only
# (a) FEEDS the verified Block A knowledge tree + an instructions blob as grounding, and (b)
# CALIBRATEs each structural claim the corpus asserts by a deterministic fact-match. The TAG
# is a pure function of (claim, facts) — the LLM authored the claim, the machine assigns the
# tier. Crucially the tier confirms STRUCTURE (the cited tuple exists), never the concept the
# prose wraps around it (a structural match is necessary, never sufficient, for a semantic
# claim) — so an LLM cannot launder a false assertion by citing a true-but-irrelevant node.

# Trust tiers (assigned by tier(), never by the LLM):
STRUCTURE_CONFIRMED = "STRUCTURE_CONFIRMED"  # the cited tuple is present; CONCEPT unverified
UNCONFIRMED = "UNCONFIRMED"  # no match in an OPEN-world family -> UNKNOWN, never "false"
CONTRADICTED = "CONTRADICTED"  # no match in a CLOSED-world family (dormant in v0)
SEMANTIC = "SEMANTIC"  # names no fact family -> a pure hypothesis the judge self-verifies

_FEED_SCHEMA = "codas.semantic_feed/v1"
_CALIBRATION_SCHEMA = "codas.semantic_calibration/v1"

_FEED_INSTRUCTIONS = (
    "You are generating an advisory semantic wiki over a VERIFIED knowledge tree. Rules: "
    "(1) cite a node-id `<path>::<class>::<symbol>` (or a bare path for a module/package) "
    "for every STRUCTURAL claim, in a fenced ```atlas:claims block (defines/calls/contains). "
    "(2) A structural match confirms only that the tuple EXISTS — never that your concept "
    "label or prose is true; treat your own concept text as unverified. "
    "(3) The tree is an OPEN-WORLD sound LOWER BOUND: a missing node/edge means UNKNOWN, "
    "never 'false' (absence is not denial). Do not assert completeness. "
    "(4) Capability/intent labels with no structural backing are hypotheses; suggest, never "
    "verify or upgrade them."
)


def _calls_index(tree: dict[str, Any]) -> dict[str, set[str]]:
    """node-id -> the set of callee node-ids it has a calls_out edge to (for `calls` claims)."""
    return {
        node_id: {edge["target"] for edge in node.get("calls_out") or []}
        for node_id, node in tree.items()
    }


def tier(
    claim: Any, node_ids: set[str], calls_index: dict[str, set[str]]
) -> str:
    """The DETERMINISTIC trust tier for one structural ``claim`` (pure; §17-clean).

    ``defines``/``contains`` resolve against knowledge-tree node PRESENCE (the family
    ``contains``); ``calls`` resolves against a tree calls_out edge (the family ``calls``).
    A present tuple is STRUCTURE_CONFIRMED; an absent one is tiered by the family's WORLD
    (``world_of``): OPEN -> UNCONFIRMED (never "false"), CLOSED -> CONTRADICTED, unknown ->
    SEMANTIC. The CONCEPT a ``defines`` claim carries is NEVER confirmed here.
    """
    if claim.kind == "calls":
        present = claim.object in calls_index.get(claim.subject, ())
        return STRUCTURE_CONFIRMED if present else _absent("calls")
    if claim.kind in ("defines", "contains"):
        present = claim.subject in node_ids
        return STRUCTURE_CONFIRMED if present else _absent("contains")
    return SEMANTIC  # unknown claim kind names no fact family


def _absent(family: str) -> str:
    world = world_of(family)
    if world == "open":
        return UNCONFIRMED
    if world == "closed":
        return CONTRADICTED
    return SEMANTIC


def _claim_row(claim: Any, verdict: str) -> dict[str, Any]:
    return {
        "kind": claim.kind,
        "subject": claim.subject,
        "object": claim.object,
        # concept is ALWAYS unverified prose, even when the tuple is STRUCTURE_CONFIRMED.
        "concept": claim.concept,
        "tier": verdict,
        "source": claim.source,
        "line": claim.line,
    }


def calibrate(ctx: ScanContext) -> list[dict[str, Any]]:
    """Tier every structural claim in the offline semantic corpus against the facts.

    Deterministic, OFFLINE: returns a sorted list of tag rows; instantiates NO ``Finding``
    and never affects ``codas check`` — CONTRADICTED (dormant in v0) is metadata only.
    """
    tree = build_atlas_tree(ctx.repo)["tree"]
    node_ids = set(tree)
    calls_index = _calls_index(tree)
    claims = ctx.semantic_corpus_claims().claims
    rows = [_claim_row(claim, tier(claim, node_ids, calls_index)) for claim in claims]
    rows.sort(
        key=lambda row: (row["kind"], row["subject"], row["object"], row["source"], row["line"])
    )
    return rows


def run_calibrate(repo: Path) -> dict[str, Any]:
    """Build the ScanContext and calibrate the offline corpus (read-only; mutates nothing)."""
    config = load_codas_config(repo / ".codas" / "config.yml")
    ctx = build_scan_context(repo, config)
    return {"schema": _CALIBRATION_SCHEMA, "calibration": calibrate(ctx)}


def build_feed(repo: Path) -> dict[str, Any]:
    """The FEED bundle a host agent generates the semantic corpus over: the verified Block A
    knowledge tree + the instructions blob. Pure projection, no LLM, out of the inventory
    hash (the tree already carries its own ``source_inventory_hash``)."""
    tree = build_atlas_tree(repo)
    return {
        "schema": _FEED_SCHEMA,
        "instructions": _FEED_INSTRUCTIONS,
        # convenience alias of knowledge_tree.open_world, hoisted to the top so a consumer
        # sees the lower-bound caveat without descending — it is the SAME object, not a
        # second source.
        "open_world": tree["open_world"],
        "knowledge_tree": tree,
    }
