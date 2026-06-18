# Design — P5 D1: wiki claim parser

Authority: plan §2 (wiki claim → governance fact only when evidence + authority
verify), §2.1 (Orientation: wiki not a fact source by itself), §5 (Wiki module
inputs/outputs), §6 (canonical wiki-claim shape `claim:wiki:<slug>`), §17 (wiki
follows inventory). Builds on the existing markdown adapter and the ScanContext
seam.

> **Folded codex design review (`af9ac6b`).** Two BLOCKERs fixed below: (1)
> `markdown._normalize` drops bare directories (`src/codas/`), extensionless
> scripts (`scripts/codas`) and globs (`.trellis/tasks/**`) — all real wiki
> evidence/canonical paths — so D1 uses its own `_wiki_normalize` (slash-only is
> enough; `*` allowed) and reuses only `_candidates`/`_resolve`/`KNOWN_EXTS`. (2)
> glob `exists` via `(repo/path).exists()` is always False → add a `path_kind`
> field (`literal`|`glob`) and compute `exists` per kind (glob → any `repo.glob`
> match). NITs folded: `_concept_slug` drops its unused param; `_heading` strips
> trailing `#`. All four claim kinds kept (the real wiki uses each).

## What a wiki claim is (deterministic, no-LLM)

The §6 example is a semantic triple (`subject/predicate/object`). Extracting that
from prose needs an LLM → forbidden for P5 correctness (§17). The deterministic,
faithful realization: a wiki page asserts **path references in a structural role**,
and the role is recoverable from the page's *section structure* — which is fixed
and authored, not freeform. So a `WikiClaim` is `(concept, kind, path)` where:

| `kind`            | parsed from                                  | D2 will verify (next slice) against         |
|-------------------|----------------------------------------------|---------------------------------------------|
| `canonical_source`| `index.md` `## Canonical Sources` bullets    | config authoritative/supporting (authority) |
| `concept_page`    | `index.md` `## Concepts` link bullets        | page exists + concept registered            |
| `evidence`        | concept page `Evidence:` bullets             | artifact/inventory facts (path exists)      |
| `sync_target`     | `## Required Synchronization` bullets        | structure `must_update_if_changed` reverse  |

D1 only **parses + records** these (with a cheap `exists` filesystem fact + a
`path_kind`). All verification (and thus any finding) is D2 → D1 facts-only,
`check . = 0`.

### `doc_claims` / `stale_claim` overlap (folded SHOULD)

Wiki `.md` files are already scanned by the markdown adapter, so every wiki link /
code-span path is *already* a `doc_claim`, and the existing `stale_claim` policy
already flags a broken wiki link (e.g. a `## Concepts` link to a not-yet-created
concept page). D1 changes none of that. "D1 is facts-only" means D1 adds **no new
policy and no new finding** — the new `wiki_claims` block is read by nobody until
D2. The block's value over `doc_claims` is the *semantic role* (`kind`) + `concept`
+ `path_kind`, which D2 verifies against authored facts (authority, structure
units), not mere file existence.

## Adapter: `src/codas/adapters/wiki.py`

New file under the existing `src/codas/adapters` (`codas-adapters` unit) — no new
structure unit, no `unowned` change. Wiki section-role semantics are wiki-specific
(orientation_layer), so per §11 ("a concept that only makes sense in one ecosystem
belongs in an adapter") they live in an adapter, not core. Reuses the markdown
adapter's `_candidates`/`_resolve`/`KNOWN_EXTS` by import (same unit) — no
re-definition, so `duplicate_implementation` cannot fire. `_normalize` is NOT
reused (too strict for wiki paths); `_wiki_normalize` replaces it.

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from codas.adapters.markdown import KNOWN_EXTS, _candidates, _resolve

WIKI_ROOT_DEFAULT = ".codas/wiki"

# Section heading (lowercased) -> claim kind for path refs found under it.
_SECTION_KIND = {
    "canonical sources": "canonical_source",
    "concepts": "concept_page",
    "required synchronization": "sync_target",
}
_EVIDENCE_LABEL = "evidence:"          # inline label line inside concept pages
# Like markdown._PATH_RE but also allows '*' so glob refs (.trellis/tasks/**) pass.
_WIKI_PATH_RE = re.compile(r"^[\w./*-]+$")


@dataclass(frozen=True)
class WikiClaim:
    source: str
    line: int
    concept: str
    kind: str        # canonical_source | concept_page | evidence | sync_target
    path: str
    path_kind: str   # literal | glob
    exists: bool


@dataclass(frozen=True)
class WikiClaims:
    claims: tuple[WikiClaim, ...]
    skipped: tuple[str, ...]


def extract_wiki_claims(
    repo: Path, files: tuple[str, ...], wiki_root: str = WIKI_ROOT_DEFAULT
) -> WikiClaims:
    """Parse structured path assertions from the Atlas Wiki markdown.

    Scoped to `.md` under ``wiki_root``. The current ``##``/``###`` section (and an
    inline ``Evidence:`` label) classifies each path reference into a claim
    ``kind``; references in unrecognized sections are left to ``doc_claims`` /
    ``stale_claim``. Fence-aware and deterministic (stable sort).
    """
    prefix = wiki_root.rstrip("/") + "/"
    wiki_files = [
        f for f in files if f.endswith(".md") and (f == wiki_root or f.startswith(prefix))
    ]
    claims: list[WikiClaim] = []
    skipped: list[str] = []
    seen: set[tuple] = set()

    for source in sorted(wiki_files):
        try:
            text = (repo / source).read_text(errors="ignore")
        except OSError:
            skipped.append(source)
            continue
        concept = _concept_slug(source)
        section: str | None = None
        in_evidence = False
        in_fence = False
        for lineno, raw in enumerate(text.splitlines(), start=1):
            stripped = raw.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            heading = _heading(stripped)
            if heading is not None:
                section = _SECTION_KIND.get(heading)
                in_evidence = False
                continue
            if stripped.lower() == _EVIDENCE_LABEL:
                in_evidence = True
                continue
            kind = "evidence" if in_evidence else section
            if kind is None:
                continue
            # concept_page: links only. path-list kinds: code spans only.
            want = "link" if kind == "concept_page" else "code"
            for cand_kind, candidate in _candidates(raw):
                if cand_kind != want:
                    continue
                normalized = _wiki_normalize(candidate, cand_kind)
                if normalized is None:
                    continue
                raw_path, _fragment = normalized
                path = _resolve(repo, source, raw_path, cand_kind)
                if path is None:
                    continue
                key = (source, lineno, kind, path)
                if key in seen:
                    continue
                seen.add(key)
                path_kind = "glob" if "*" in path else "literal"
                claims.append(
                    WikiClaim(
                        source=source, line=lineno, concept=concept, kind=kind,
                        path=path, path_kind=path_kind, exists=_exists(repo, path, path_kind),
                    )
                )

    claims.sort(key=lambda c: (c.source, c.line, c.kind, c.path))
    return WikiClaims(claims=tuple(claims), skipped=tuple(sorted(skipped)))


def _wiki_normalize(candidate: str, kind: str) -> tuple[str, str] | None:
    """Like markdown._normalize but wiki-permissive: a code span needs only a slash
    (bare dirs, extensionless scripts, globs all qualify), and '*' is allowed."""
    text = candidate.strip().replace("\\", "/")
    if not text or "://" in text or text.startswith("#") or text.startswith("mailto:"):
        return None
    head, _, fragment = text.partition("#")
    path, _, _query = head.partition("?")
    if not path or " " in path or "\t" in path or not _WIKI_PATH_RE.match(path):
        return None
    has_slash = "/" in path
    has_ext = path.endswith(KNOWN_EXTS)
    if kind == "code":
        if not has_slash:        # any slashed path: dir, extensionless, glob, file
            return None
    elif not (has_ext or has_slash):   # link
        return None
    return path, fragment


def _exists(repo: Path, path: str, path_kind: str) -> bool:
    if path_kind == "glob":
        return any(True for _ in repo.glob(path))
    return (repo / path).exists()


def _concept_slug(source: str) -> str:
    import posixpath
    return posixpath.splitext(posixpath.basename(source))[0]


def _heading(stripped: str) -> str | None:
    if not stripped.startswith("#"):
        return None
    return stripped.strip("#").strip().lower()   # tolerate trailing ATX '#'
```

Notes / traces (verified against the real wiki):
- `index.md` `## Canonical Sources`: each `` `path` `` code span emitted as
  `canonical_source` — including the now-fixed `src/codas/`-style dirs, extensionless
  `scripts/codas`, and the glob `.trellis/tasks/**` (`path_kind="glob"`,
  `exists` via `repo.glob`).
- `index.md` `## Concepts`: each `[label](concepts/foo.md)` link emitted as
  `concept_page` (link resolves source-relative via `_resolve` →
  `.codas/wiki/concepts/foo.md`).
- concept page: each `Evidence:` label flips state so following code-span paths are
  `evidence` until the next `##`; `## Required Synchronization` paths are
  `sync_target`.
- `## Bootstrap Rule` fenced block ignored (fence-aware).
- Helper names `_wiki_normalize`, `_exists`, `_concept_slug`, `_heading` + constant
  `_WIKI_PATH_RE` verified unique top-level under `src/` (`grep -rn "^def _wiki_normalize\|^def _exists\|^def _concept_slug\|^def _heading" src/codas` → none).

## Inventory: `structure/inventory.py`

Add a `wiki_claims` block after `doc_claims`, same shape (`sources` + records +
`skipped`). The bridge already imports adapters directly (it is
`codas-structure-module`, allowed). Read the wiki root from config, default
otherwise.

```python
from codas.adapters.wiki import extract_wiki_claims
...
wiki_root = (config.raw.get("wiki") or {}).get("path", ".codas/wiki")
wiki_claims = extract_wiki_claims(repo, tuple(files), wiki_root)
inventory["wiki_claims"] = {
    "sources": sorted({c.source for c in wiki_claims.claims}),
    "claims": [
        {"source": c.source, "line": c.line, "concept": c.concept, "kind": c.kind,
         "path": c.path, "path_kind": c.path_kind, "exists": c.exists}
        for c in wiki_claims.claims
    ],
    "skipped": list(wiki_claims.skipped),
}
```

(`config` is already loaded at the top of `build_inventory`.)

## Seam: `facts/context.py`

```python
from codas.adapters.wiki import WikiClaim, WikiClaims, extract_wiki_claims
# __all__ += ["WikiClaim", "WikiClaims"]

def wiki_claims(self) -> WikiClaims:
    """Atlas Wiki structural claims for the scanned tree (cached, adapter-sorted)."""
    if "wiki_claims" not in self._cache:
        wiki_root = (self.config.raw.get("wiki") or {}).get("path", ".codas/wiki")
        self._cache["wiki_claims"] = extract_wiki_claims(self.repo, self.files, wiki_root)
    return self._cache["wiki_claims"]
```

The seam stays the single off-`adapters` importer of an adapter. D2's policy will
call `ctx.wiki_claims()` and never import `codas.adapters.wiki`.

## Determinism / dogfooding

- Deterministic: scoped + sorted file list, stable claim sort, `exists`/`path_kind`
  are pure reads, no timestamp → `inventory --json` byte-identical across runs.
  (`repo.glob` results are not used for ordering, only for the boolean `exists`.)
- New file `adapters/wiki.py` lives under the owned `src/codas/adapters` dir → no
  `unowned` growth, no structure unit needed.
- No new governance file / config source / document role (wiki files + the `wiki:`
  config block already exist and are registered).
- New public symbols `WikiClaim`, `WikiClaims`, `extract_wiki_claims` + privates —
  unique under `src/`.
- `check . = 0`: facts-only, no policy added; consumers are only the inventory
  bridge and the seam accessor; glob/dir handling cannot raise during inventory.

## Tests (`tests/test_wiki_claims.py`)

- **Fixture wiki**: temp repo `.codas/wiki/index.md` (`## Canonical Sources` with an
  existing file path, a directory `src/`, an extensionless `scripts/run`, a glob
  `data/**`, and a missing `gone.py`; `## Concepts` link to a concept page) +
  `.codas/wiki/concepts/foo.md` (`Evidence:` list + `## Required Synchronization`).
  Assert parsed `(concept, kind, path, path_kind, exists)` tuples exactly — covering
  **directory, extensionless, glob** paths (the folded BLOCKER) and existing vs
  missing.
- **Fence-aware**: a backtick path inside a fenced code block is ignored.
- **Scoping**: a `## Canonical Sources` heading in a NON-wiki `.md` (outside
  `wiki_root`) yields no wiki claim.
- **stale_claim boundary** (folded SHOULD): a missing concept-page link produces NO
  `wiki_claims` finding (D1 has no policy) — test comment notes the existing
  `stale_claim`/`doc_claims` path is what would flag it, not wiki_claims.
- **Determinism**: two `extract_wiki_claims` calls return equal results.
- **Real-repo smoke** (subprocess `inventory --json`): `wiki_claims` block exists,
  has `canonical_source` claims from `index.md` (incl. the `.trellis/tasks/**` glob
  with `path_kind="glob"`) and `evidence` claims from a concept page; byte-identical
  across two runs.
- **check regression**: `codas check .` stays 0.

## Open questions — resolved (codex `af9ac6b`)

1. **Vocabulary** — keep all four kinds; the real wiki uses each.
2. **Reuse markdown privates** — reuse `_candidates`/`_resolve`/`KNOWN_EXTS`; do NOT
   reuse `_normalize` (too strict) → own `_wiki_normalize`.
3. **`exists`** — keep, defined per `path_kind` (literal → `Path.exists`, glob →
   any `repo.glob` match).
4. **Section detection** — exact lowercased heading match; a renamed section just
   drops the claim (a D2/D3 stale-wiki concern), no fuzzy matching in D1.
5. **Wiki root** — inline `config.raw["wiki"]["path"]` (default `.codas/wiki`);
   typed config field deferred until a third call site.
