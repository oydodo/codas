# Prove W3 end-to-end — host-agent judge contract + dogfood worked example

## Status
IN PROGRESS → docs-only (no new core code; the W3 machinery `--emit-feed`/`--calibrate` shipped
in S3). Non-gate. De-risks the project's #1 risk (unproven demand / unvalidated loop) by
documenting AND dogfooding the full host-agent judge loop.

## Goal
Make the W3 semantic loop usable + proven: a written host-agent JUDGE CONTRACT (the feed →
author → calibrate → judge loop + the trust-tier discipline) AND a real worked example produced
by actually running the loop on a Codas subsystem (dogfood, host agent = me).

## What shipped
- CONTRACT.md `## The W3 semantic judge loop (host-agent contract)`: the 4-step loop, the iron
  rules (cite a node-id; STRUCTURE_CONFIRMED confirms the tuple not the concept; ABSTAIN on
  UNCONFIRMED; never upgrade; suggestion-only/never-committed; work subsystem-by-subsystem
  because the feed is large), and a WORKED EXAMPLE dogfooded on the calibration layer itself —
  including the laundering demo ("tier implements a neural ranking model" → STRUCTURE_CONFIRMED on
  the tuple, concept flagged false by the judge) and an UNCONFIRMED node the judge abstains on.
- CONTRACT.md `## Author workflow`: the full `codas wiki` surface (emit-pack/-tree/-feed,
  calibrate, emit-mermaid/-html, write/verify) documented.

## Validation (the "proof")
Ran the real loop on src/codas/app/calibrate.py + adapters/semantic.py: `--emit-feed` →
authored a real corpus under `.codas/cache/semantic/` (gitignored, removed after) → `--calibrate`
→ judged. Confirmed STRUCTURE_CONFIRMED for real tuples, UNCONFIRMED for an absent node, and the
laundering defense (a false concept on a true tuple stays STRUCTURE_CONFIRMED, concept unverified).

## Acceptance
- [ ] CONTRACT.md documents the loop + the discipline + a worked example.
- [ ] The example is REAL (produced by running the loop), not invented.
- [ ] `codas check .` 0 (no new unresolved doc-claims from CONTRACT.md); full suite green;
      inventory byte-identical; wiki --verify clean.
- [ ] No core code change; no gate change; the corpus stays ephemeral (gitignored, uncommitted).
