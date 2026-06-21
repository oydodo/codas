"""Config-driven product scope (wiki.product_roots) — the cross-repo enabler.

Pins the resolver (default + override + normalization) and that the knowledge tree / pack
scope to the CONFIGURED roots, not a hardcoded `src/codas/` — so the wiki outputs cover any
repo's layout (a `lib/`-layout repo renders a non-empty tree).
"""
from __future__ import annotations

import unittest

from codas.app.wiki import (
    _PRODUCT_ROOTS_DEFAULT,
    product_roots,
    project_atlas_pack,
    project_atlas_tree,
)


def _inv(defs):
    return {
        "symbols": {"definitions": [
            {"module": m, "name": n, "kind": "function", "line": 1} for m, n in defs
        ]},
        "imports": {"edges": []},
        "calls": {"edges": []},
        "units": [
            {"id": "lib", "path": "lib", "kind": "package", "owner": "O"},
            {"id": "root", "path": ".", "kind": "repo", "owner": "O"},
        ],
    }


class ResolverTests(unittest.TestCase):
    def test_default_when_unset(self):
        self.assertEqual(product_roots({}), _PRODUCT_ROOTS_DEFAULT)
        self.assertEqual(product_roots({"wiki": {}}), _PRODUCT_ROOTS_DEFAULT)
        self.assertEqual(_PRODUCT_ROOTS_DEFAULT, ("src",))

    def test_override_and_normalization(self):
        raw = {"wiki": {"product_roots": ["lib", "  app/ ", ".\\pkg"]}}
        self.assertEqual(product_roots(raw), ("lib", "app", ".\\pkg".replace("\\", "/").strip("/")))

    def test_empty_list_falls_back_to_default(self):
        self.assertEqual(product_roots({"wiki": {"product_roots": []}}), _PRODUCT_ROOTS_DEFAULT)


class ScopeTests(unittest.TestCase):
    def test_tree_scoped_to_configured_roots(self):
        # symbols under lib/ AND tests/ — only the configured root's nodes appear.
        inv = _inv([("lib/foo.py", "run"), ("tests/test_x.py", "t")])
        tree = project_atlas_tree(inv, ("lib",))["tree"]
        self.assertIn("lib/foo.py::::run", tree)
        self.assertIn("lib/foo.py", tree)          # module node
        self.assertIn("lib", tree)                  # package node
        self.assertNotIn("tests/test_x.py::::t", tree)  # tests excluded — not a product root

    def test_cross_repo_nonempty_tree(self):
        # A non-src/codas layout still renders a non-empty tree when its root is configured.
        inv = _inv([("lib/foo.py", "run")])
        tree = project_atlas_tree(inv, ("lib",))["tree"]
        self.assertTrue(tree)
        # the pack's symbol_index is likewise scoped
        pack = project_atlas_pack(inv, ("lib",))
        self.assertEqual([s["module"] for s in pack["symbol_index"]], ["lib/foo.py"])

    def test_root_not_configured_yields_empty(self):
        inv = _inv([("lib/foo.py", "run")])
        self.assertEqual(project_atlas_tree(inv, ("nonexistent",))["tree"], {})
        self.assertEqual(project_atlas_pack(inv, ("nonexistent",))["symbol_index"], [])


if __name__ == "__main__":
    unittest.main()
