import contextlib
import copy
import io
import json
import unittest
from pathlib import Path

from codas.app.wiki import build_atlas_tree, project_atlas_tree
from codas.cli import main

# A minimal hand-crafted inventory exercising every projection rule of the neutral
# knowledge tree: product scoping, authoritative symbol kinds, call-endpoint-derived
# method nodes + class containers, product<->product edge filtering, resolution-tagged
# adjacency, and longest-prefix (sibling-safe) ownership.
MINI = {
    "symbols": {
        "definitions": [
            # product-scoped top-level class + function (authoritative kinds)
            {"module": "src/codas/app/svc.py", "name": "Service", "kind": "class", "line": 5},
            {"module": "src/codas/app/svc.py", "name": "helper", "kind": "function", "line": 30},
            # sibling of the `src/codas/app` unit: must NOT be owned by it
            {"module": "src/codas/apple.py", "name": "Apple", "kind": "class", "line": 1},
            # OUT of product scope -> excluded entirely
            {"module": "tests/test_svc.py", "name": "TestSvc", "kind": "class", "line": 1},
        ],
        "skipped": [],
    },
    "calls": {
        "edges": [
            # a method (caller_class=Service) calls a module-level function: yields the
            # method node, the Service class container, and a resolution-tagged edge.
            {
                "caller_module": "codas.app.svc", "caller_class": "Service",
                "caller_symbol": "run", "caller_path": "src/codas/app/svc.py", "caller_line": 10,
                "callee_module": "codas.app.svc", "callee_class": "",
                "callee_symbol": "helper", "callee_path": "src/codas/app/svc.py", "callee_line": 30,
                "resolution": "direct",
            },
            # edge to a NON-product callee -> dropped (both endpoints must be in scope)
            {
                "caller_module": "codas.app.svc", "caller_class": "",
                "caller_symbol": "helper", "caller_path": "src/codas/app/svc.py", "caller_line": 30,
                "callee_module": "vendor.lib", "callee_class": "",
                "callee_symbol": "ext", "callee_path": "vendor/lib.py", "callee_line": 1,
                "resolution": "imported_symbol",
            },
        ],
        "skipped": [],
    },
    "units": [
        {"id": "repo-root", "path": ".", "kind": "area", "owner": "Core"},
        {"id": "codas-source", "path": "src/codas", "kind": "package", "owner": "Core"},
        {"id": "codas-app", "path": "src/codas/app", "kind": "package", "owner": "App Team"},
    ],
}


class ProjectKnowledgeTreeTests(unittest.TestCase):
    def setUp(self):
        self.result = project_atlas_tree(MINI)
        self.tree = self.result["tree"]

    def test_schema_and_open_world(self):
        self.assertEqual(self.result["schema"], "codas.knowledge_tree/v1")
        self.assertTrue(self.result["open_world"]["is_lower_bound"])
        self.assertTrue(self.result["open_world"]["misses"])  # named calls gaps
        # the pure projection never pins the hash; build_atlas_tree adds it.
        self.assertNotIn("source_inventory_hash", self.result)

    def test_out_of_scope_symbol_excluded(self):
        self.assertNotIn("tests/test_svc.py::::TestSvc", self.tree)
        self.assertNotIn("tests/test_svc.py", self.tree)

    def test_top_level_symbol_nodes(self):
        cls = self.tree["src/codas/app/svc.py::::Service"]
        self.assertEqual(cls["kind"], "class")
        self.assertEqual(cls["path"], "src/codas/app/svc.py")
        self.assertEqual(cls["symbol"], "Service")
        fn = self.tree["src/codas/app/svc.py::::helper"]
        self.assertEqual(fn["kind"], "function")
        self.assertEqual(fn["symbol"], "helper")

    def test_method_node_and_class_containment(self):
        method_id = "src/codas/app/svc.py::Service::run"
        self.assertIn(method_id, self.tree)
        self.assertEqual(self.tree[method_id]["kind"], "function")
        # the method is a child of its class container, not of the module
        self.assertEqual(
            self.tree["src/codas/app/svc.py::::Service"]["children"], [method_id]
        )

    def test_module_and_package_hierarchy(self):
        module = self.tree["src/codas/app/svc.py"]
        self.assertEqual(module["kind"], "module")
        self.assertIsNone(module["symbol"])
        # module children = the two top-level (cls=="") nodes, sorted
        self.assertEqual(
            module["children"],
            ["src/codas/app/svc.py::::Service", "src/codas/app/svc.py::::helper"],
        )
        self.assertIn("src/codas/app/svc.py", self.tree["src/codas/app"]["children"])
        self.assertIn("src/codas/app", self.tree["src/codas"]["children"])
        # src/codas is the product root: a package, owned, parent of nothing above it
        self.assertEqual(self.tree["src/codas"]["kind"], "package")

    def test_resolution_tagged_adjacency(self):
        run = self.tree["src/codas/app/svc.py::Service::run"]
        self.assertEqual(
            run["calls_out"],
            [{"target": "src/codas/app/svc.py::::helper", "resolution": "direct"}],
        )
        helper = self.tree["src/codas/app/svc.py::::helper"]
        self.assertEqual(
            helper["calls_in"],
            [{"source": "src/codas/app/svc.py::Service::run", "resolution": "direct"}],
        )

    def test_non_product_edge_dropped(self):
        # the helper -> vendor.ext edge is excluded; vendor node never created
        self.assertNotIn("vendor/lib.py::::ext", self.tree)
        self.assertEqual(self.tree["src/codas/app/svc.py::::helper"]["calls_out"], [])

    def test_longest_prefix_ownership(self):
        # the more specific src/codas/app unit wins over src/codas
        for node_id in (
            "src/codas/app/svc.py",
            "src/codas/app/svc.py::::Service",
            "src/codas/app/svc.py::Service::run",
        ):
            self.assertEqual(self.tree[node_id]["unit_id"], "codas-app")
            self.assertEqual(self.tree[node_id]["unit_owner"], "App Team")
        # the product-root package falls to src/codas, not the repo-root unit
        self.assertEqual(self.tree["src/codas"]["unit_id"], "codas-source")

    def test_sibling_prefix_not_owned(self):
        # src/codas/apple.py must NOT be owned by the src/codas/app unit (sibling-safe)
        apple = self.tree["src/codas/apple.py::::Apple"]
        self.assertEqual(apple["unit_id"], "codas-source")
        self.assertEqual(apple["unit_owner"], "Core")

    def test_constructor_call_does_not_relabel_class(self):
        # a top-level class is authoritative `class`; a call edge that uses it as a
        # callee (a `Foo()` constructor, callee_class="") must NOT relabel it `function`.
        inv = {
            "symbols": {
                "definitions": [
                    {"module": "src/codas/x.py", "name": "Foo", "kind": "class", "line": 1},
                    {"module": "src/codas/x.py", "name": "make", "kind": "function", "line": 9},
                ],
                "skipped": [],
            },
            "calls": {
                "edges": [
                    {
                        "caller_module": "codas.x", "caller_class": "",
                        "caller_symbol": "make", "caller_path": "src/codas/x.py", "caller_line": 9,
                        "callee_module": "codas.x", "callee_class": "",
                        "callee_symbol": "Foo", "callee_path": "src/codas/x.py", "callee_line": 1,
                        "resolution": "direct",
                    },
                ],
                "skipped": [],
            },
            "units": [],
        }
        tree = project_atlas_tree(inv)["tree"]
        foo = tree["src/codas/x.py::::Foo"]
        self.assertEqual(foo["kind"], "class")
        # and the constructor call shows up as calls_in on the class node
        self.assertEqual(
            foo["calls_in"],
            [{"source": "src/codas/x.py::::make", "resolution": "direct"}],
        )

    def test_empty_and_degenerate_inventory(self):
        self.assertEqual(project_atlas_tree({})["tree"], {})
        # explicit-None blocks must not raise (the `or {}` / `or []` guards)
        degenerate = project_atlas_tree(
            {"symbols": None, "calls": None, "units": None}
        )
        self.assertEqual(degenerate["tree"], {})
        self.assertEqual(degenerate["schema"], "codas.knowledge_tree/v1")

    def test_pure_and_deterministic(self):
        before = copy.deepcopy(MINI)
        first = project_atlas_tree(MINI)
        second = project_atlas_tree(MINI)
        self.assertEqual(first, second)
        self.assertEqual(MINI, before)  # input not mutated


class BuildKnowledgeTreeTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()

    def test_build_on_self_shape(self):
        tree = build_atlas_tree(self.repo)
        self.assertEqual(tree["schema"], "codas.knowledge_tree/v1")
        self.assertTrue(tree["open_world"]["is_lower_bound"])
        self.assertTrue(tree["source_inventory_hash"].startswith("sha256:"))
        self.assertTrue(tree["tree"])  # non-empty
        kinds = {node["kind"] for node in tree["tree"].values()}
        self.assertEqual(kinds, {"package", "module", "class", "function"})

    def test_build_byte_identical(self):
        a = json.dumps(build_atlas_tree(self.repo), indent=2, sort_keys=True)
        b = json.dumps(build_atlas_tree(self.repo), indent=2, sort_keys=True)
        self.assertEqual(a, b)


class WikiEmitTreeCliTests(unittest.TestCase):
    def test_emit_tree_prints_json(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["wiki", str(Path.cwd()), "--emit-tree"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        for key in ("schema", "tree", "source_inventory_hash", "open_world"):
            self.assertIn(key, payload)
        self.assertEqual(payload["schema"], "codas.knowledge_tree/v1")

    def test_emit_tree_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as caught:
            main(["wiki", str(Path.cwd()), "--emit-tree", "--emit-pack"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
