"""``codas status`` — per-turn injection (gap 3): the neutral, advisory changed-file core.

Covers the design-review folds: B1 (since-baseline catches committed-by-a-worker changes
the working-tree diff is blind to), B2 (the precise duplicate-symbol predicate + its src-only
limitation), S1 (factual, never imperative), S2 (dedup), S3 (capped payload), S5 (never
raises), S9 (no-baseline distinguished from clean)."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from codas.app.status import (
    _MAX_BYTES,
    _MAX_LINES,
    StatusResult,
    inject_context,
    read_baseline,
    record_baseline,
    render_additional_context,
    render_text,
    run_status,
)

_MAP_PARTIAL_DEPRECATED = """\
version: 1
kind: structure_map
units:
  codas-unit:
    path: .codas
    kind: governance_state
    owner: Core
    purpose: x
    canonical_placement: x
  src-owned:
    path: src/owned
    kind: package
    owner: Core
    purpose: x
    canonical_placement: x
deprecated_paths:
  old-pkg:
    path: src/legacy
    replacement: src/new
    status: deprecated
"""

_CONFIG = "version: 1\n"

_MAP_ROOT = """\
version: 1
kind: structure_map
units:
  repo-root:
    path: .
    kind: repository
    owner: Core
    purpose: x
    canonical_placement: x
"""

# Owns .codas + src/owned, but NOT src/orphan.py — so a file there is genuinely unowned.
_MAP_PARTIAL = """\
version: 1
kind: structure_map
units:
  codas-unit:
    path: .codas
    kind: governance_state
    owner: Core
    purpose: x
    canonical_placement: x
  src-owned:
    path: src/owned
    kind: package
    owner: Core
    purpose: x
    canonical_placement: x
"""

_MAP_DEPRECATED = """\
version: 1
kind: structure_map
units:
  repo-root:
    path: .
    kind: repository
    owner: Core
    purpose: x
    canonical_placement: x
deprecated_paths:
  old-pkg:
    path: src/legacy
    replacement: src/new
    status: deprecated
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(tmp: str, *, structure: str = _MAP_ROOT) -> Path:
    repo = Path(tmp)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _write(repo / ".codas" / "config.yml", _CONFIG)
    _write(repo / ".codas" / "structure.yml", structure)
    return repo


def _commit_all(repo: Path, message: str = "c") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class ChangedFileFilterTests(unittest.TestCase):
    def test_clean_committed_tree_has_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")
            _commit_all(repo)  # collision exists, but tree is clean vs HEAD

            result = run_status(repo)

            self.assertEqual(result.git, "ok")
            self.assertEqual(result.findings, ())

    def test_duplicate_symbol_caught_when_a_changed_file_collides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")
            _commit_all(repo)
            # b.py is a NEW (untracked) file re-defining handle — the changed side.
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")

            result = run_status(repo)

            kinds = {f["kind"] for f in result.findings}
            self.assertEqual(kinds, {"duplicate-symbol"})
            # Only the changed file's side is reported (a.py is committed/unchanged).
            self.assertEqual([f["path"] for f in result.findings], ["src/b.py"])
            self.assertIn("also defined in src/a.py", result.findings[0]["message"])

    def test_pre_existing_collision_in_unchanged_file_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")
            _commit_all(repo)
            # Change an unrelated file; the a/b collision is untouched.
            _write(repo / "src" / "c.py", "def solo():\n    pass\n")

            result = run_status(repo)

            self.assertEqual(result.findings, ())

    def test_missing_owner_caught_for_changed_unowned_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp, structure=_MAP_PARTIAL)
            _commit_all(repo)  # establish HEAD baseline
            _write(repo / "src" / "orphan.py", "x = 1\n")  # new, unowned

            result = run_status(repo)

            self.assertEqual(
                [(f["kind"], f["path"]) for f in result.findings],
                [("missing-structure-owner", "src/orphan.py")],
            )

    def test_deprecated_path_caught_for_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp, structure=_MAP_DEPRECATED)
            _commit_all(repo)  # establish HEAD baseline
            _write(repo / "src" / "legacy" / "old.py", "x = 1\n")

            result = run_status(repo)

            self.assertIn(
                ("deprecated-path-used", "src/legacy/old.py"),
                [(f["kind"], f["path"]) for f in result.findings],
            )

    def test_path_scope_filters_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp, structure=_MAP_PARTIAL)
            _commit_all(repo)  # establish HEAD baseline
            _write(repo / "src" / "orphan.py", "x = 1\n")

            self.assertEqual(run_status(repo, paths=("tests",)).findings, ())
            self.assertEqual(
                [f["path"] for f in run_status(repo, paths=("src",)).findings],
                ["src/orphan.py"],
            )


class SinceBaselineTests(unittest.TestCase):
    """B1: a worker that COMMITS before returning leaves a clean tree vs HEAD; the
    working-tree diff is blind to it, but the session-baseline diff is not."""

    def test_committed_change_blind_to_working_tree_but_seen_since_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")
            baseline = _commit_all(repo)
            # A "worker" adds a colliding symbol AND commits it -> clean tree vs HEAD.
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")
            _commit_all(repo)

            # Working-tree diff (HEAD) sees nothing.
            self.assertEqual(run_status(repo).findings, ())
            # Baseline diff surfaces the committed collision.
            since = run_status(repo, since=baseline)
            self.assertEqual([f["path"] for f in since.findings], ["src/b.py"])

    def test_record_and_read_baseline_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            head = _commit_all(repo)

            recorded = record_baseline(repo)

            self.assertEqual(recorded, head)
            self.assertEqual(read_baseline(repo), head)


class GitPreconditionTests(unittest.TestCase):
    """S9: distinguish a clean tree from a repo with no git baseline."""

    def test_non_git_repo_is_no_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / ".codas" / "config.yml", _CONFIG)
            _write(repo / ".codas" / "structure.yml", _MAP_ROOT)

            result = run_status(repo)

            self.assertEqual(result.git, "no-baseline")
            self.assertIn("no git baseline", render_text(result))

    def test_repo_with_no_commits_is_no_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)  # git init, but nothing committed

            self.assertEqual(run_status(repo).git, "no-baseline")
            self.assertIsNone(record_baseline(repo))


class NeverRaisesTests(unittest.TestCase):
    """S5: status must never crash the turn it advises."""

    def test_broken_config_yields_empty_error_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            (repo / ".codas" / "config.yml").write_text("version: 1\n  bad: indent\n")

            result = run_status(repo)

            self.assertEqual(result.findings, ())
            self.assertEqual(result.git, "error")

    def test_missing_codas_dir_yields_error_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)  # no .codas at all
            self.assertEqual(run_status(repo).git, "error")

    def test_inject_context_never_raises_on_broken_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(inject_context(repo), "")


class FactualPhrasingTests(unittest.TestCase):
    """S1: no imperative recommendation leaks into the injected text."""

    _IMPERATIVES = ("Add a", "Move it", "Consolidate", "declare a", "add a waiver")

    def test_no_imperative_in_messages_or_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # All THREE policy message paths fire (missing-owner + duplicate + deprecated-path),
            # so the imperative blacklist below is exercised against every kind, not just two.
            repo = _init_repo(tmp, structure=_MAP_PARTIAL_DEPRECATED)
            _commit_all(repo)  # establish HEAD baseline so findings actually fire
            _write(repo / "src" / "orphan.py", "x = 1\n")  # missing-owner
            _write(repo / "src" / "owned" / "a.py", "def reuse():\n    pass\n")  # duplicate
            _write(repo / "src" / "owned" / "b.py", "def reuse():\n    pass\n")
            _write(repo / "src" / "legacy" / "old.py", "y = 1\n")  # deprecated-path

            result = run_status(repo)
            kinds = {f["kind"] for f in result.findings}
            self.assertEqual(
                kinds,
                {"missing-structure-owner", "duplicate-symbol", "deprecated-path-used"},
            )
            blob = render_text(result) + "\n" + render_additional_context(result)

            for imperative in self._IMPERATIVES:
                self.assertNotIn(imperative, blob, imperative)


class PayloadCapTests(unittest.TestCase):
    """S3: the injected additionalContext is hard-capped (lines + bytes)."""

    def _many(self, n: int) -> StatusResult:
        rows = tuple(
            {"path": f"src/f{i}.py", "kind": "missing-structure-owner",
             "message": f"Artifact has no owning Structure Unit: src/f{i}.py"}
            for i in range(n)
        )
        return StatusResult(rows, "ok", n)

    def test_caps_lines_and_appends_more_tail(self) -> None:
        text = render_additional_context(self._many(_MAX_LINES + 5))
        body = [ln for ln in text.splitlines() if ln.startswith("- ")]
        self.assertLessEqual(len([ln for ln in body if "more" not in ln]), _MAX_LINES)
        self.assertTrue(any("+5 more" in ln for ln in body))

    def test_respects_byte_cap(self) -> None:
        text = render_additional_context(self._many(200))
        # header + capped finding lines + tail; the finding body stays within the budget.
        self.assertLessEqual(len(text.encode("utf-8")), _MAX_BYTES + 80)

    def test_empty_when_clean(self) -> None:
        self.assertEqual(render_additional_context(StatusResult((), "ok", 0)), "")

    def test_oversized_single_finding_emits_nothing_not_header_only(self) -> None:
        # A single finding larger than the byte cap must not produce a header+tail with zero
        # shown lines (N4) — it injects nothing rather than non-actionable noise.
        huge = StatusResult(
            ({"path": "src/x.py", "kind": "duplicate-symbol", "message": "x" * (_MAX_BYTES + 10)},),
            "ok",
            1,
        )
        self.assertEqual(render_additional_context(huge), "")

    def test_oversized_row_does_not_block_smaller_rows(self) -> None:
        rows = (
            {"path": "src/big.py", "kind": "k", "message": "B" * (_MAX_BYTES + 10)},
            {"path": "src/small.py", "kind": "k", "message": "small finding"},
        )
        text = render_additional_context(StatusResult(rows, "ok", 2))
        self.assertIn("small finding", text)
        self.assertNotIn("B" * 50, text)


class DedupTests(unittest.TestCase):
    """S2: a standing finding is injected once per session, not on every return."""

    def test_inject_then_reinject_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp, structure=_MAP_PARTIAL)
            _commit_all(repo)
            _write(repo / "src" / "orphan.py", "x = 1\n")

            first = inject_context(repo)
            self.assertIn("src/orphan.py", first)
            # Same standing finding -> already seen -> nothing re-injected.
            self.assertEqual(inject_context(repo), "")

    def test_record_baseline_resets_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp, structure=_MAP_PARTIAL)
            _commit_all(repo)
            _write(repo / "src" / "orphan.py", "x = 1\n")

            self.assertIn("src/orphan.py", inject_context(repo))
            record_baseline(repo)  # new session -> seen cleared
            self.assertIn("src/orphan.py", inject_context(repo))


class DedupCapInteractionTests(unittest.TestCase):
    """S1×S3: a finding capped out of one turn's payload must NOT be marked seen — it has to
    surface on a later turn, not be silently dropped after being counted in '+K more'."""

    def test_capped_out_findings_surface_on_a_later_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp, structure=_MAP_PARTIAL)
            _commit_all(repo)
            record_baseline(repo)
            extra = 3
            for i in range(_MAX_LINES + extra):
                _write(repo / "src" / f"orphan{i}.py", "x = 1\n")  # all unowned

            first = inject_context(repo)
            self.assertEqual(first.count("Artifact has no owning"), _MAX_LINES)
            self.assertIn(f"+{extra} more", first)

            # Turn 2: only the capped-out findings remain unseen -> they now inject.
            second = inject_context(repo)
            self.assertEqual(second.count("Artifact has no owning"), extra)
            self.assertNotIn("more", second)

            # Turn 3: everything has been surfaced -> nothing left.
            self.assertEqual(inject_context(repo), "")


class StaleBaselineTests(unittest.TestCase):
    """S2/S9: an unresolvable --since baseline (rebase/squash orphan) is surfaced, not
    silently degraded to a clean-looking working-tree run."""

    def test_unresolvable_since_reports_stale_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _commit_all(repo)

            result = run_status(repo, since="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")

            self.assertEqual(result.git, "stale-baseline")
            self.assertIn("did not resolve", render_text(result))


class BothSidesChangedTests(unittest.TestCase):
    """B2 fan-out: when BOTH colliding modules are in the changed set, each side is reported."""

    def test_both_colliding_modules_changed_reports_each(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _commit_all(repo)  # baseline
            _write(repo / "src" / "a.py", "def handle():\n    pass\n")  # both new/untracked
            _write(repo / "src" / "b.py", "def handle():\n    pass\n")

            dup = [f for f in run_status(repo).findings if f["kind"] == "duplicate-symbol"]

            self.assertEqual(sorted(f["path"] for f in dup), ["src/a.py", "src/b.py"])
            self.assertIn("also defined in src/b.py", _find(dup, "src/a.py")["message"])
            self.assertIn("also defined in src/a.py", _find(dup, "src/b.py")["message"])


def _find(rows: list[dict], path: str) -> dict:
    return next(r for r in rows if r["path"] == path)


class DuplicateSymbolScopeTests(unittest.TestCase):
    """B2: the duplicate-symbol pillar is src-only (matches the policy's SCOPE_PREFIX)."""

    def test_non_src_collision_not_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(tmp)
            _commit_all(repo)  # establish HEAD baseline so lib/* land in the changed set
            _write(repo / "lib" / "a.py", "def handle():\n    pass\n")
            _write(repo / "lib" / "b.py", "def handle():\n    pass\n")

            result = run_status(repo)
            # The lib files ARE in the changed set (non-vacuous: 2 untracked files seen)...
            self.assertGreaterEqual(result.affected_count, 2)
            # ...yet duplicate_symbol is src-only, so the collision is not reported.
            dup = [f for f in result.findings if f["kind"] == "duplicate-symbol"]
            self.assertEqual(dup, [])


if __name__ == "__main__":
    unittest.main()
