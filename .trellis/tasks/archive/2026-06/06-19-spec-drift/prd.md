# P5 spec_drift policy (diff-grounded, materiality-as-claim)

## Goal

Implement the declared-but-unimplemented `spec_drift` policy (severity `error`):
"Changes to behavior, architecture, commands, policies or data model must update
their authoritative claim source." This is the first **diff-based** policy in Codas
and closes the dogfood gap proven twice this session (a design change landed while
its claim sources went stale, and nothing fired).

## The architecture (why the obvious design is wrong)

The Structure Map's `must_update_if_changed` reads, per the authoritative schema
(`docs/codas-structure-map-schema.html` §4): *"Docs, specs, wiki pages or config
files that should change **when this unit changes materially**."* So the unit's own
change is the trigger; the listed paths are required reactions — and the obligation
is scoped to **material** changes.

"Material" is a **semantic** judgment (a one-line comment edit vs a behavior rewrite).
Codas's correctness core may not judge it (§17 no-LLM). The naive proxy — "any edit
is material" — is unfaithful and breaks the dogfood gate: implementing this very
policy edits `src/codas/policies` + `src/codas/app`, which would then demand editing
`docs/codas-implementation-plan.html` in the same commit.

Root cause (user's framing): Codas's "changed" signal today is hash/file-level —
binary; it knows *that* a file changed, not *how*. Materiality needs the diff **and**
a judgment. So:

> **Codas grounds it (the diff), the host agent judges it (material?), Codas verifies
> it (is the required reaction present in the diff?).** — the wiki pattern, applied to
> drift.

This splits the contract into two faithful layers:

- `must_update_if_changed` (structure.yml) = **coarse, advisory** co-change hints
  (any-edit, materiality unknown). **Never a hard gate.** (Advisory surfacing is a
  later/optional facet; not built in v0.)
- A **vouched drift coupling** (someone — agent or human — judged this co-change
  obligation genuinely material) = the **gating** rule, verified deterministically
  against the diff. Faithful, because materiality was vouched, not blindly assumed.

## Scope (v0 — the diff substrate + the claim verifier)

1. **Diff substrate** — new git adapter `codas.adapters.git.extract_changed_paths(repo)
   -> tuple[str, ...]`: working-tree paths differing from HEAD (tracked diff ∪
   untracked), repo-relative posix, sorted, `-z` NUL-parsed. Returns `()` for a
   non-git dir / missing git / no-HEAD baseline. Pure stdlib `subprocess`. Surfaced via
   `ScanContext.changed_paths()` (memoized). **Not** serialized into `inventory` — it
   reflects dirty working-tree state and would break the byte-identical inventory
   invariant; it is a policy-time fact.

2. **Claim verifier** — `codas.policies.spec_drift.check_spec_drift(ctx)`: reads vouched
   drift couplings from `.codas/claims.yml` (new optional `drift_couplings` list) and
   verifies each against `ctx.changed_paths()`. A coupling whose `when_changed` site is
   in the diff but whose required reaction is absent → `error` finding. No autonomous
   materiality judgment. No couplings (the live repo's state) → `[]`.

Drift coupling shape (`.codas/claims.yml`):

```yaml
drift_couplings:
  - when_changed: <repo-rel path or glob>     # the change site that was judged material
    requires: [<repo-rel path or glob>, ...]  # reactions that must co-change in the diff
    owner: <responsible owner>
    reason: <why this co-change obligation is material / enforced>
```

Semantics: if **any** changed path matches `when_changed` and **any** `requires`
entry has **no** matching changed path → one finding per unmet (coupling, requirement).

## Out of scope (documented, deferred)

- **Autonomous `must_update_if_changed` gating** — needs materiality judgment
  (semantic) → belongs to the host agent, who reads the diff and promotes a genuinely
  material hint into a vouched `drift_coupling`. v0 does not auto-gate on it; an
  advisory surfacing (e.g. via preflight) is a later facet.
- **Hunk-level diff / "how it changed"** — v0 grounds at file level (`changed_paths`).
  The host agent reads the actual `git diff` content itself to judge materiality; Codas
  need not surface hunks.
- **`documents.yml` `updates_when` semantic triggers** and **`--since <ref>` range
  diffs** (CI/P6 hooks).
- **Prose staleness** (unanchored README text) — not machine-verifiable; anchor-to-facts
  is tracked separately.

## Requirements

- `extract_changed_paths` deterministic given tree state; `()` on non-git/no-HEAD.
- `ScanContext.changed_paths()` memoized; absent from `inventory`.
- `check_spec_drift(ctx)` reads `drift_couplings`, glob-aware match, deterministic
  total-key sort; `error` severity (matches policies.yml).
- Wire into `run_check`; patch the orchestration one-ctx-forwarded contract test.
- Tolerate a malformed/absent `drift_couplings` gracefully (no crash; emit a load-error
  finding only if `claims.yml` itself fails to load, consistent with
  `duplicate_implementation`).

## Acceptance Criteria

- [ ] `codas check .` on the clean committed tree = 0 (live `claims.yml` has no
      `drift_couplings`; resting gate green).
- [ ] Fixture: a coupling whose `when_changed` is in the diff and a `requires` reaction
      is absent → exactly one `spec-drift` finding (evidence names the coupling + the
      missing reaction).
- [ ] Fixture: `when_changed` + all `requires` present in the diff → 0.
- [ ] Fixture: `when_changed` not in the diff → 0 (coupling dormant).
- [ ] `extract_changed_paths`: tracked-modify, untracked-add, deleted-file all surface;
      non-git dir → `()`; filenames with spaces survive `-z` parsing.
- [ ] `inventory --json` byte-identical across two processes (changed_paths absent).
- [ ] Full unittest suite green; orchestration contract test patched for spec_drift.
- [ ] Dogfood self-check stays 0 with the policy live (impl commit touches only
      `src/**` + `tests/**`; no `drift_couplings` authored).

## Notes

- Diff-based half of the **drift vs stale** split (memory `codas-wiki-architecture`):
  DRIFT = change-triggered (this policy); STALE = state-based (`stale_claim`,
  `stale_wiki_claim`).
- Same engine split as the wiki: Codas grounds (diff) + verifies (reaction present);
  the host agent supplies the semantic judgment (materiality) as a vouched claim.
