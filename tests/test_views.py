import contextlib
import io
import unittest
from pathlib import Path

from codas.app.render_util import mermaid_label
from codas.app.views import (
    _html_escape,
    _render_nav,
    _tree_roots,
    build_html,
    build_mermaid,
)
from codas.cli import main


class HelperTests(unittest.TestCase):
    def test_mermaid_label_sanitizes(self):
        # no double-quote or newline survives (would break the ["..."] label / determinism)
        out = mermaid_label('a"b\nc\\d')
        self.assertNotIn('"', out)
        self.assertNotIn("\n", out)
        self.assertEqual(out, "a'b c/d")

    def test_mermaid_label_neutralizes_syntax_chars(self):
        # bracket/angle/backtick chars that would break Mermaid node syntax are replaced
        out = mermaid_label("foo[bar]<baz>`q`")
        for ch in ("[", "]", "<", ">", "`"):
            self.assertNotIn(ch, out)

    def test_render_nav_cycle_guard(self):
        # a cyclic tree must NOT infinite-recurse (defensive; the real tree is acyclic)
        cyclic = {
            "a": {"kind": "package", "unit_owner": None, "children": ["b"]},
            "b": {"kind": "module", "unit_owner": None, "children": ["a"]},
        }
        html = "\n".join(_render_nav(cyclic, "a", 0))  # must terminate
        self.assertIn("<code>a</code>", html)
        self.assertIn("<code>b</code>", html)

    def test_html_escape(self):
        self.assertEqual(_html_escape('<a & "b">'), "&lt;a &amp; &quot;b&quot;&gt;")

    def test_tree_roots(self):
        tree = {
            "pkg": {"kind": "package", "children": ["pkg/m.py"]},
            "pkg/m.py": {"kind": "module", "children": []},
        }
        self.assertEqual(_tree_roots(tree), ["pkg"])

    def test_render_nav_nests_and_escapes(self):
        tree = {
            "pkg": {"kind": "package", "unit_owner": "Team <X>", "children": ["pkg/m.py"]},
            "pkg/m.py": {"kind": "module", "unit_owner": None, "children": []},
        }
        html = "\n".join(_render_nav(tree, "pkg", 0))
        self.assertIn("<code>pkg</code>", html)
        self.assertIn("Team &lt;X&gt;", html)  # owner escaped
        self.assertIn("<code>pkg/m.py</code>", html)


class MermaidTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()
        self.out = build_mermaid(self.repo)

    def test_byte_identical(self):
        self.assertEqual(self.out, build_mermaid(self.repo))

    def test_structure_and_caveat(self):
        self.assertIn("graph LR", self.out)
        # the open-world caveat appears as a %% comment AND a visible node
        self.assertIn("%% OPEN-WORLD", self.out)
        self.assertIn("owCaveat[", self.out)
        self.assertIn("LOWER BOUND", self.out)
        # edges are nX --> nY
        self.assertRegex(self.out, r"\n  n\d+ --> n\d+")


class HtmlTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path.cwd()
        self.out = build_html(self.repo)

    def test_byte_identical(self):
        self.assertEqual(self.out, build_html(self.repo))

    def test_caveat_rendered_and_self_contained(self):
        self.assertIn("OPEN-WORLD", self.out)
        self.assertIn('class="caveat"', self.out)
        self.assertIn('class="mermaid"', self.out)
        # self-contained: NO external script / CDN / network reference (security + determinism)
        self.assertNotIn("<script", self.out)
        self.assertNotIn("<link", self.out)
        self.assertNotIn("http://", self.out)
        self.assertNotIn("https://", self.out)

    def test_well_formed_skeleton(self):
        self.assertTrue(self.out.startswith("<!DOCTYPE html>"))
        self.assertTrue(self.out.rstrip().endswith("</html>"))


class ViewsCliTests(unittest.TestCase):
    def _run(self, *flags):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(["wiki", str(Path.cwd()), *flags])
        return code, buffer.getvalue()

    def test_emit_mermaid_cli(self):
        code, out = self._run("--emit-mermaid")
        self.assertEqual(code, 0)
        self.assertIn("graph LR", out)

    def test_emit_html_cli(self):
        code, out = self._run("--emit-html")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("<!DOCTYPE html>"))

    def test_views_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as caught:
            main(["wiki", str(Path.cwd()), "--emit-mermaid", "--emit-tree"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
