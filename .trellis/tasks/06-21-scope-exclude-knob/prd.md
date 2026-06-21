# First-class codas scope-exclude knob — decouple hash-scope from gitignore

## Goal

Give Codas a NATIVE "committed but NOT in the byte-identical inventory hash" lever, decoupled
from `.gitignore`. Today the ONLY way to keep a tracked file out of the hash is to gitignore it
(which also stops it being committed) or to hard-code a bespoke exclusion (`_IGNORE_PATHS`
receipts/cache, the W7 `derived_output_prefixes` book root). So "don't commit" and "don't
govern/hash" are wrongly BOUND. This task adds a config `scope.exclude` (name TBD) so a path can
be **committed + tracked yet excluded from the inventory hash + scan**, without gitignoring it.

## Why NOT just switch to an include-whitelist

`workspace.roots` is already an include-whitelist (defaulted to `["."]`, which is why Codas
appears to "scan everything"). Flipping to a tight whitelist would lose **default-govern**: a
new file under a governed root is governed by default, which `missing_owner` relies on to
guarantee no ungoverned code can be slipped in. Default-govern is a SAFETY property for a
governance tool. So: keep "everything under roots is governed unless explicitly excused"; make
the EXCUSE lever first-class and gitignore-independent. (The canonical-layout / tighter-roots
idea is the SEPARATE backlog task `06-21-canonical-layout`.)

## Approach — generalize W7

W7 shipped exactly the prototype: `wiki.book_root` -> `structure/index.derived_output_prefixes`
+ the public `is_derived_output(path, prefixes)` predicate, threaded as DATA through the scanner
(`filter_to_roots`/`_walk_files`/`discover_files`/`build_artifact_index`) + `head_snapshot` + the
`ScanContext` seam + the existence sites. Generalize that single-purpose `book_root` into a
GENERAL `scope.exclude` list (the book root becomes one entry / a default). The threading +
existence-guard machinery already exists from W7 — this is mostly a config-resolver generalization
+ folding `_IGNORE_PATHS` (receipts/cache) and `book_root` into the one knob.

## Requirements

- R1 — a config `scope.exclude` (repo-relative paths/prefixes) resolved by a single resolver
  (generalizing `derived_output_prefixes`); a path under it is excluded from the scan + the
  inventory hash + every claim/role existence site, WITHOUT needing a `.gitignore` entry.
- R2 — default-govern preserved: a file under `workspace.roots` and NOT under `scope.exclude` is
  still governed (missing_owner unchanged); the exclude is opt-in per path.
- R3 — fold the existing bespoke exclusions into the one mechanism where sensible: the W7
  `wiki.book_root` (keep as a default/alias), and consider `_IGNORE_PATHS` (receipts/cache).
  Backward-compatible: Codas's own config stays byte-identical.
- R4 — works on BOTH scan paths (git `ls-files --others` AND the non-git walk fallback) — the W7
  `is_derived_output` already covers both via `filter_to_roots` + `_walk_files`.
- R5 — determinism: `codas check` 0, inventory byte-identical 2x, verify clean, full suite green;
  §11/§17 clean.

## Acceptance Criteria

- [ ] A path listed in `scope.exclude` is committed/tracked yet absent from the inventory hash +
      scan + existence resolution, with no `.gitignore` entry.
- [ ] A path NOT excluded and under roots is still governed (missing_owner still fires on it).
- [ ] W7 `wiki.book_root` behavior preserved (folded in or aliased); Codas config byte-identical.
- [ ] Both git and non-git scan paths honor the knob.
- [ ] check 0; inventory byte-identical 2x; verify clean; suite green; §11/§17 clean.

## Notes

- **Gate-semantics** (changes the scan/hash scope = the byte-identical core) -> codex DESIGN
  review BEFORE implementation, THEN codex IMPL review. See [[never-skip-trellis-for-low-risk]].
- Directly simplifies the injection-MVP BLOCKER#1: `.codas/.install-state.json` could be declared
  in `scope.exclude` instead of gitignore + `_IGNORE_PATHS` (cleaner) — but that task ships first
  with the gitignore fix; this knob can later subsume it.
- Open design Qs for the design pass: exact knob name/shape (`scope.exclude` list vs a richer
  block); whether to subsume `_IGNORE_PATHS` (receipts/cache are walk-only + regenerable — may
  stay separate); how `scope.exclude` interacts with `exclude_under` (the wiki-pack self-reference
  filter); whether excluded-but-tracked needs a new inventory marker (probably not).
</content>
