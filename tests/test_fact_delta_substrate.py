"""spec-drift v2-A: fact-snapshot at an arbitrary git source + fact-delta substrate.

Locks the contracts the substrate adds on top of the byte-identical fact extractors
(which test_call_facts / test_python_import_facts / test_python_adapter / test_inventory
already pin as golden values): a HEAD snapshot that is a pure function of (file-set,
content); a pure identity-key delta; the ScanContext accessors; and the codex
design-review conditions (no partial HEAD snapshot, target_path in the import key,
decode alignment, set-derived package soundness).
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from codas.adapters.callgraph import extract_call_facts_from_parsed
from codas.adapters.python import extract_symbol_facts_from_parsed
from codas.adapters.python_parse import parse_python_modules, parse_sources
from codas.config.loader import CodasConfig
from codas.facts.context import build_scan_context
from codas.facts.delta import diff_snapshots
from codas.facts.snapshot import FactSnapshot, head_snapshot, snapshot_from_parsed
from codas.structure.index import discover_files


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


def _commit(repo: Path, msg: str = "c") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _config(repo: Path) -> CodasConfig:
    return CodasConfig(path=repo / ".codas" / "config.yml", raw={})


_PKG_INIT = ""
_PKG_A = "from pkg.b import helper\n\n\ndef run():\n    helper()\n"
_PKG_B = "def helper():\n    pass\n"


def _make_pkg(repo: Path) -> None:
    _write(repo / "pkg" / "__init__.py", _PKG_INIT)
    _write(repo / "pkg" / "a.py", _PKG_A)
    _write(repo / "pkg" / "b.py", _PKG_B)


class ParseSourcesTests(unittest.TestCase):
    def test_parse_sources_matches_disk_parse(self) -> None:
        # parse_sources (pre-read text) must produce the same module set/order as
        # parse_python_modules (disk read) so the HEAD snapshot equals a disk snapshot.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _make_pkg(repo)
            files = ("pkg/__init__.py", "pkg/a.py", "pkg/b.py")
            disk = parse_python_modules(repo, files)
            sources = {f: (repo / f).read_bytes().decode("utf-8", "ignore") for f in files}
            mem = parse_sources(sources)
            self.assertEqual([m.path for m in disk.modules], [m.path for m in mem.modules])
            self.assertEqual(
                extract_symbol_facts_from_parsed(disk),
                extract_symbol_facts_from_parsed(mem),
            )

    def test_parse_sources_skips_non_py_and_records_parse_failure(self) -> None:
        parsed = parse_sources({"a.py": "def f():\n  pass\n", "b.py": "def (", "c.txt": "x"})
        by_path = {m.path: m for m in parsed.modules}
        self.assertEqual(sorted(by_path), ["a.py", "b.py"])  # .txt dropped
        self.assertIsNotNone(by_path["a.py"].tree)
        self.assertIsNone(by_path["b.py"].tree)  # syntax error -> skipped


class HeadSnapshotTests(unittest.TestCase):
    def test_head_snapshot_equals_clean_working_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)
            _commit(repo)
            head = head_snapshot(repo, (".",))
            files = tuple(discover_files(repo, (".",)))
            working = snapshot_from_parsed(parse_python_modules(repo, files))
            self.assertEqual(head, working)  # clean tree: HEAD == working

    def test_head_snapshot_none_without_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)  # never committed -> HEAD unresolved
            self.assertIsNone(head_snapshot(repo, (".",)))

    def test_head_snapshot_none_when_not_a_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(head_snapshot(Path(tmp), (".",)))

    def test_head_snapshot_filters_to_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)
            _write(repo / "outside" / "__init__.py", "")
            _write(repo / "outside" / "z.py", "def gone():\n    pass\n")
            _commit(repo)
            snap = head_snapshot(repo, ("pkg",))
            modules = {d.module for d in snap.symbols.definitions}
            self.assertTrue(all(m.startswith("pkg/") for m in modules))
            self.assertNotIn("outside/z.py", modules)

    def test_head_snapshot_none_on_blob_read_failure(self) -> None:
        # Codex B1: a single failed blob read must abandon the WHOLE snapshot, never
        # return a partial one (a missing file would read as "removed" facts = false drift).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)
            _commit(repo)
            with mock.patch("codas.facts.snapshot.read_blob_at_head", return_value=None):
                self.assertIsNone(head_snapshot(repo, (".",)))


class PackageSoundnessTests(unittest.TestCase):
    def test_call_scope_follows_file_set_not_filesystem(self) -> None:
        # Codex should-1: package membership is set-derived. With pkg/__init__.py in the
        # parsed set, pkg modules are in call-scope; drop it from the set and they fall
        # out of scope EVEN THOUGH the file still exists on disk (filesystem unchanged).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _make_pkg(repo)
            full = ("pkg/__init__.py", "pkg/a.py", "pkg/b.py")
            without_init = ("pkg/a.py", "pkg/b.py")  # __init__.py exists on disk, not in set

            with_edges = extract_call_facts_from_parsed(parse_python_modules(repo, full)).edges
            self.assertTrue(any(e.callee_symbol == "helper" for e in with_edges))

            no_edges = extract_call_facts_from_parsed(parse_python_modules(repo, without_init)).edges
            self.assertEqual(no_edges, ())  # not a package per the set -> out of scope

    def test_deleted_tracked_init_drops_package_without_crashing(self) -> None:
        # Codex blocker: a tracked __init__.py deleted from the working tree is still
        # listed by `git ls-files --cached`, so it enters the scan as a read_error
        # module. Its directory must NOT be marked a package (else the call extractor
        # re-raises the read_error and crashes a dirty repo). Exercises the REAL
        # discover_files/git path, not a manual tuple omission.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)
            _commit(repo)
            (repo / "pkg" / "__init__.py").unlink()  # delete but leave tracked
            ctx = build_scan_context(repo, _config(repo))
            self.assertIn("pkg/__init__.py", ctx.files)  # still discovered (cached)
            calls = ctx.calls()  # must not raise FileNotFoundError
            self.assertFalse(
                any(e.caller_path.startswith("pkg/") for e in calls.edges),
                "pkg dropped from call scope once its __init__.py is gone",
            )

    def test_repo_root_package_dotted_name_is_repo_relative(self) -> None:
        # repo-root __init__.py: set-derived dotted names are repo-relative (stop at
        # ""), never prepending the repo directory name the legacy absolute-path walk
        # could have climbed into.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "__init__.py", "")
            _write(repo / "a.py", "def f():\n    pass\n")
            _write(repo / "b.py", "from a import f\n\n\ndef g():\n    f()\n")
            edges = extract_call_facts_from_parsed(
                parse_python_modules(repo, ("__init__.py", "a.py", "b.py"))
            ).edges
            edge = next(e for e in edges if e.callee_symbol == "f")
            self.assertEqual(edge.caller_module, "b")
            self.assertEqual(edge.callee_module, "a")


class DiffTests(unittest.TestCase):
    def _snap(self, repo: Path, sources: dict[str, str]) -> FactSnapshot:
        for rel, text in sources.items():
            _write(repo / rel, text)
        return snapshot_from_parsed(parse_python_modules(repo, tuple(sources)))

    def test_identical_snapshots_empty_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            snap = self._snap(repo, {"pkg/__init__.py": "", "pkg/a.py": _PKG_A, "pkg/b.py": _PKG_B})
            self.assertTrue(diff_snapshots(snap, snap).is_empty())

    def test_line_shift_is_not_drift(self) -> None:
        # Identity keys drop line numbers: moving a def down must NOT register as drift.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base = self._snap(repo, {"m.py": "def f():\n    pass\n"})
            shifted = self._snap(repo, {"m.py": "# a comment\n\n\ndef f():\n    pass\n"})
            self.assertTrue(diff_snapshots(base, shifted).is_empty())

    def test_added_and_removed_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base = self._snap(repo, {"m.py": "def old():\n    pass\n"})
            head = self._snap(repo, {"m.py": "def new():\n    pass\n"})
            delta = diff_snapshots(base, head)
            self.assertEqual(delta.symbols_added, (("m.py", "new", "function"),))
            self.assertEqual(delta.symbols_removed, (("m.py", "old", "function"),))

    def test_import_key_keeps_target_path(self) -> None:
        # Codex B2: target_path is in the import identity, so a first-party<->external
        # resolution flip is real drift (dependency_direction reads target_path).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            # base: target.py present -> import resolves first-party (has a path)
            base = self._snap(repo, {
                "pkg/__init__.py": "", "pkg/a.py": "from pkg.t import x\n", "pkg/t.py": "x = 1\n",
            })
            # head: same importer, target.py absent from the set -> resolves external (None)
            for rel, text in {"pkg/__init__.py": "", "pkg/a.py": "from pkg.t import x\n"}.items():
                _write(repo / rel, text)
            head = snapshot_from_parsed(parse_python_modules(repo, ("pkg/__init__.py", "pkg/a.py")))
            delta = diff_snapshots(base, head)
            added = dict((m, tp) for (m, t, tp) in delta.imports_added if t == "pkg.t")
            removed = dict((m, tp) for (m, t, tp) in delta.imports_removed if t == "pkg.t")
            self.assertEqual(removed.get("pkg/a.py"), "pkg/t.py")  # was first-party
            self.assertEqual(added.get("pkg/a.py"), None)          # now external


class ScanContextDeltaTests(unittest.TestCase):
    def test_clean_tree_empty_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)
            _commit(repo)
            ctx = build_scan_context(repo, _config(repo))
            self.assertTrue(ctx.fact_delta().is_empty())

    def test_staged_added_symbol_shows_in_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)
            _commit(repo)
            _write(repo / "pkg" / "b.py", _PKG_B + "\n\ndef extra():\n    pass\n")
            ctx = build_scan_context(repo, _config(repo))
            delta = ctx.fact_delta()
            self.assertIn(("pkg/b.py", "extra", "function"), delta.symbols_added)
            self.assertEqual(delta.symbols_removed, ())

    def test_no_head_reads_everything_as_added(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _init(repo)
            _make_pkg(repo)  # never committed -> no baseline
            ctx = build_scan_context(repo, _config(repo))
            delta = ctx.fact_delta()
            self.assertIn(("pkg/b.py", "helper", "function"), delta.symbols_added)
            self.assertEqual(delta.symbols_removed, ())

    def test_working_snapshot_reuses_memoized_facts(self) -> None:
        repo = Path.cwd()
        ctx = build_scan_context(repo, _config(repo))
        snap = ctx.working_snapshot()
        self.assertEqual(snap.symbols, ctx.symbols())
        self.assertEqual(snap.imports, ctx.imports())
        self.assertEqual(snap.calls, ctx.calls())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
