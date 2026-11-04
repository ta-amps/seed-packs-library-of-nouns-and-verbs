"""Reading, type inference, profiling, validation and outlier flags on small made-up tables."""

from __future__ import annotations

import statistics
import unittest

from csv_checks import flag, kind_of, profile, read_csv, validate

REQUEST = {
    "dataset": {"name": "t", "sha256": "0" * 64, "delimiter": ",", "description": "made-up"},
    "columns": [
        {"name": "day", "type": "date", "required": True},
        {"name": "team", "type": "string", "required": True, "allowed": ["a", "b"]},
        {"name": "count", "type": "integer", "required": True, "min": 0, "max": 100},
        {"name": "weight", "type": "number", "required": False, "min": 0},
        {"name": "code", "type": "string", "required": False, "pattern": "[A-Z]{2}[0-9]", "unique": True},
        {"name": "email", "type": "string", "required": False, "identifying": True},
    ],
    "missing_tokens": ["", "NA"],
    "outlier_rule": {"method": "tukey_fences", "k": 1.5, "quantiles": "inclusive", "min_values": 4},
}
HEADER = "day,team,count,weight,code,email"


def table(*rows: str, header: str = HEADER, prefix: bytes = b""):
    return read_csv(prefix + ("\r\n".join([header, *rows]) + "\r\n").encode("utf-8"))


class Reading(unittest.TestCase):
    def test_kinds_are_the_narrowest_that_parse(self) -> None:
        cases = {"12": "integer", "-3": "integer", "1.5": "number", ".5": "number", "2e3": "number",
                 "2026-02-28": "date", "2026-02-30": "string", "true": "boolean", "True": "string", "twelve": "string",
                 "1,000": "string", "12 ": "string"}
        for raw, kind in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(kind_of(raw), kind)

    def test_byte_order_mark_quotes_and_ragged_rows(self) -> None:
        t = table('2026-01-01,a,"4",1.5,AB1,x@example.invalid', "2026-01-02,b,5", prefix=b"\xef\xbb\xbf")
        self.assertTrue(t.bom)
        self.assertEqual(t.header[0], "day")
        self.assertEqual(t.rows[0][2], "4")
        self.assertEqual(t.ragged_rows, [2])

    def test_quoted_commas_and_line_breaks_stay_in_one_field(self) -> None:
        t = table('2026-01-01,a,4,1,AB1,"a, b\r\nc"')
        self.assertEqual(len(t.rows), 1)
        self.assertEqual(t.rows[0][5], "a, b\r\nc")

    def test_an_empty_file_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            read_csv(b"")
        with self.assertRaises(UnicodeDecodeError):
            read_csv(b"day\r\n\xff\r\n")


class Profiling(unittest.TestCase):
    def test_profile_counts_and_hides_identifying_values(self) -> None:
        t = table("2026-01-01,a,4,1.5,AB1,x@example.invalid", "2026-01-02,b,NA,2,AB2,y@example.invalid",
                  "2026-01-02,b,NA,2,AB2,y@example.invalid", "2026-01-03,a,seven,3,AB3,")
        p = profile(t, REQUEST)
        columns = {c["name"]: c for c in p["columns"]}
        self.assertEqual(columns["count"]["inferred_type"], "string")
        self.assertEqual(columns["count"]["type_counts"], {"integer": 1, "string": 1})
        self.assertEqual(columns["count"]["missing"], 2)
        self.assertEqual((columns["weight"]["min"], columns["weight"]["max"]), (1.5, 3.0))
        self.assertEqual((columns["day"]["min"], columns["day"]["max"]), ("2026-01-01", "2026-01-03"))
        self.assertEqual(columns["email"]["examples"], [])
        self.assertIsNone(columns["email"]["min"])
        self.assertEqual(columns["email"]["distinct"], 2)
        self.assertEqual(p["duplicate_rows"], [{"row": 3, "same_as": 2}])
        self.assertNotIn("x@example.invalid", repr(p))

    def test_header_findings(self) -> None:
        p = profile(table("1,2,3", header="day,,day"), REQUEST)
        self.assertEqual(p["duplicate_headers"], ["day"])
        self.assertEqual(p["blank_headers"], [2])


class Validation(unittest.TestCase):
    def test_each_rule_is_reported_once_with_its_row(self) -> None:
        t = table(
            "2026-01-01,a,4,1.5,AB1,x@example.invalid",
            "2026-02-30,a,4,1.5,AB2,x@example.invalid",    # type: not a real date
            "2026-01-03,c,4,1.5,AB3,",                      # allowed
            "2026-01-04,a,,1.5,AB4,",                       # required
            "2026-01-05,a,101,-1,AB5,",                     # max and min
            "2026-01-06,a,seven,,ab6,",                     # type and pattern
            "2026-01-07,a,4,,AB1,",                         # unique
        )
        report = validate(t, REQUEST)
        found = [(v["row"], v["column"], v["rule"]) for v in report["violations"]]
        self.assertEqual(found, [
            (2, "day", "type"), (3, "team", "allowed"), (4, "count", "required"), (5, "count", "max"),
            (5, "weight", "min"), (6, "code", "pattern"), (6, "count", "type"), (7, "code", "unique"),
        ])
        self.assertEqual(report["counts"], {"allowed": 1, "max": 1, "min": 1, "pattern": 1, "required": 1, "type": 2, "unique": 1})
        self.assertEqual((report["rows_with_violations"], report["passed"]), (6, False))

    def test_identifying_values_never_appear(self) -> None:
        request = {**REQUEST, "columns": [*REQUEST["columns"][:5], {**REQUEST["columns"][5], "required": True}]}
        report = validate(table("2026-01-01,a,4,1.5,AB1,"), request)
        self.assertEqual(report["violations"], [{"row": 1, "column": "email", "rule": "required", "value": None}])

    def test_header_problems_and_ragged_rows(self) -> None:
        report = validate(table("2026-01-01,a,4,extra", header="day,team,count,note"), REQUEST)
        self.assertIn("column 'note' is not declared", report["header_problems"])
        self.assertIn("declared column 'weight' is not in the header", report["header_problems"])
        self.assertFalse(report["passed"])
        self.assertEqual(validate(table("2026-01-01,a,4"), REQUEST)["violations"][0]["rule"], "row_length")


class Flags(unittest.TestCase):
    def test_fences_match_hand_computed_quartiles(self) -> None:
        counts = [10, 12, 11, 13, 12, 95, 11, 12]
        rows = [f"2026-01-0{i + 1},a,{c},1,AB{i},," for i, c in enumerate(counts)]
        rows = [row[:-1] for row in rows]
        report = flag(table(*rows), REQUEST)
        entry = next(o for o in report["outliers"] if o["column"] == "count")
        q1, _, q3 = statistics.quantiles(counts, n=4, method="inclusive")
        self.assertEqual((entry["q1"], entry["q3"]), (q1, q3))
        self.assertEqual((q1, q3), (11.0, 12.25))     # inclusive: positions (n - 1) p, interpolated
        self.assertEqual((entry["low_fence"], entry["high_fence"]), (9.125, 14.125))
        self.assertEqual((entry["rows"], entry["values"]), ([6], [95]))

    def test_missing_values_and_too_few_values(self) -> None:
        report = flag(table("2026-01-01,a,,1,AB1,", "2026-01-02,a,NA,2,AB2,", "2026-01-03,a,3,x,AB3,"), REQUEST)
        missing = {m["column"]: m for m in report["missing"]}
        self.assertEqual(missing["count"], {"column": "count", "count": 2, "rows": [1, 2]})
        weight = next(o for o in report["outliers"] if o["column"] == "weight")
        self.assertEqual((weight["values_used"], weight["reason"], weight["rows"]), (2, "too_few_values", []))

    def test_a_bad_rule_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            flag(table("2026-01-01,a,1,1,AB1,"), {**REQUEST, "outlier_rule": {**REQUEST["outlier_rule"], "k": 0}})


if __name__ == "__main__":
    unittest.main()
