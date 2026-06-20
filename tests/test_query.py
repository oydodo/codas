from __future__ import annotations

import json
import unittest
from pathlib import Path

from codas.app.query import (
    QueryError,
    _rows_for,
    _row_matches,
    _scalar_str,
    kinds,
    parse_selectors,
    run_query,
    run_schema,
)

REPO = Path(__file__).resolve().parents[1]


class ParseSelectors(unittest.TestCase):
    def test_valid(self) -> None:
        self.assertEqual(
            parse_selectors(["module=codas.app", "line=10"]),
            [("module", "codas.app"), ("line", "10")],
        )

    def test_value_with_equals(self) -> None:
        # split on the FIRST = only
        self.assertEqual(parse_selectors(["k=a=b"]), [("k", "a=b")])

    def test_empty_value_allowed(self) -> None:
        self.assertEqual(parse_selectors(["caller_class="]), [("caller_class", "")])

    def test_missing_equals_raises(self) -> None:
        with self.assertRaises(QueryError):
            parse_selectors(["nofield"])

    def test_empty_field_raises(self) -> None:
        with self.assertRaises(QueryError):
            parse_selectors(["=value"])


class Matches(unittest.TestCase):
    def test_string_and_numeric(self) -> None:
        row = {"module": "codas.app", "line": 10}
        self.assertTrue(_row_matches(row, [("module", "codas.app"), ("line", "10")]))
        self.assertFalse(_row_matches(row, [("line", "11")]))

    def test_missing_field_never_matches(self) -> None:
        self.assertFalse(_row_matches({"module": "x"}, [("ghost", "anything")]))

    def test_no_selectors_matches(self) -> None:
        self.assertTrue(_row_matches({"a": 1}, []))

    def test_json_spelled_bool_and_null(self) -> None:
        # The selector value must match the JSON spelling the user sees in output:
        # bool -> true/false, None -> null (not Python True/None).
        self.assertEqual(_scalar_str(True), "true")
        self.assertEqual(_scalar_str(False), "false")
        self.assertEqual(_scalar_str(None), "null")
        self.assertEqual(_scalar_str(10), "10")
        row = {"exists": True, "package": None}
        self.assertTrue(_row_matches(row, [("exists", "true")]))
        self.assertFalse(_row_matches(row, [("exists", "True")]))  # Python spelling no longer matches
        self.assertTrue(_row_matches(row, [("package", "null")]))


class RowsFor(unittest.TestCase):
    def test_absent_block_returns_empty(self) -> None:
        # A repo with no program.yml has no "program" block.
        self.assertEqual(_rows_for({}, "work-items"), [])

    def test_present_block_empty_subkey(self) -> None:
        self.assertEqual(_rows_for({"program": {}}, "work-items"), [])


class RunQuery(unittest.TestCase):
    def test_unknown_kind_raises(self) -> None:
        with self.assertRaises(QueryError):
            run_query(REPO, "bogus", [])

    def test_symbols_filter_by_module(self) -> None:
        rows = run_query(REPO, "symbols", [("module", "src/codas/app/query.py")])
        names = sorted(r["name"] for r in rows)
        self.assertIn("run_query", names)
        self.assertIn("run_schema", names)
        self.assertTrue(all(r["module"] == "src/codas/app/query.py" for r in rows))

    def test_calls_filter(self) -> None:
        rows = run_query(REPO, "calls", [("caller_symbol", "run_impact")])
        callees = {r["callee_symbol"] for r in rows}
        self.assertIn("compute_impact", callees)

    def test_units_block_is_the_list(self) -> None:
        rows = run_query(REPO, "units", [])
        self.assertTrue(rows)
        self.assertTrue(all("id" in r for r in rows))

    def test_unmatched_selector_empty(self) -> None:
        self.assertEqual(run_query(REPO, "symbols", [("module", "no/such/path.py")]), [])

    def test_unknown_field_empty_not_error(self) -> None:
        self.assertEqual(run_query(REPO, "symbols", [("ghostfield", "x")]), [])

    def test_work_items_kind(self) -> None:
        rows = run_query(REPO, "work-items", [("phase", "P7")])
        self.assertTrue(rows)
        self.assertTrue(all(r["phase"] == "P7" for r in rows))
        self.assertIn(
            "06-20-codas-query-and-schema-p7-query-surface", rows[0]["trellis_tasks"]
        )

    def test_html_claims_json_bool_selector(self) -> None:
        # html-claims rows carry exists (bool). The clean repo has 0 missing, so
        # exists=true returns all and exists=false returns none.
        present = run_query(REPO, "html-claims", [("exists", "true")])
        self.assertTrue(present)
        self.assertEqual(run_query(REPO, "html-claims", [("exists", "false")]), [])

    def test_deterministic(self) -> None:
        a = json.dumps(run_query(REPO, "calls", []), sort_keys=True)
        b = json.dumps(run_query(REPO, "calls", []), sort_keys=True)
        self.assertEqual(a, b)


class RunSchema(unittest.TestCase):
    def test_lists_all_kinds(self) -> None:
        schema = run_schema(REPO)
        self.assertEqual(sorted(schema), kinds())

    def test_calls_fields_present(self) -> None:
        schema = run_schema(REPO)
        self.assertIn("caller_symbol", schema["calls"]["fields"])
        self.assertEqual(schema["calls"]["block"], "calls")
        self.assertEqual(schema["calls"]["rows"], "edges")

    def test_units_block_is_list(self) -> None:
        schema = run_schema(REPO)
        self.assertEqual(schema["units"]["rows"], None)
        self.assertIn("id", schema["units"]["fields"])

    def test_deterministic(self) -> None:
        a = json.dumps(run_schema(REPO), sort_keys=True)
        b = json.dumps(run_schema(REPO), sort_keys=True)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
