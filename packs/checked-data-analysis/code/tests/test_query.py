"""The recorded query language: filters, groups, aggregates, counted exclusions and digests."""

from __future__ import annotations

import unittest

from csv_checks import digest, flag, read_csv, run_queries, run_query

REQUEST = {
    "dataset": {"name": "t", "sha256": "0" * 64, "delimiter": ",", "description": "made-up"},
    "columns": [
        {"name": "team", "type": "string", "required": True, "allowed": ["a", "b"]},
        {"name": "score", "type": "integer", "required": True, "min": 0, "max": 100},
        {"name": "hours", "type": "number", "required": False},
    ],
    "missing_tokens": [""],
    "outlier_rule": {"method": "tukey_fences", "k": 1.5, "quantiles": "inclusive", "min_values": 4},
}
ROWS = ["a,10,1.5", "a,20,2.5", "b,30,", "b,40,4", "c,50,5", "a,999,1", "b,seven,2", "a,20,2.5"]
TABLE = read_csv(("team,score,hours\r\n" + "\r\n".join(ROWS) + "\r\n").encode())
FLAGS = flag(TABLE, REQUEST)


def query(**parts) -> dict:
    return {"id": "q-test", "description": "test", "filter": [], "group_by": [], **parts}


class Queries(unittest.TestCase):
    def test_valid_filters_are_counted_exclusions(self) -> None:
        out = run_query(TABLE, REQUEST, FLAGS, query(
            filter=[{"column": "team", "op": "valid"}, {"column": "score", "op": "valid"}, {"op": "not_duplicate"}],
            group_by=["team"], aggregates=[{"name": "n", "fn": "count"}, {"name": "total", "fn": "sum", "column": "score"}]))
        self.assertEqual(out["result"], [{"team": "a", "n": 2, "total": 30}, {"team": "b", "n": 2, "total": 70}])
        self.assertEqual((out["rows_in"], out["rows_after_filter"], out["excluded_by_filter"]), (8, 4, 4))

    def test_mean_median_min_max_and_present_counts(self) -> None:
        out = run_query(TABLE, REQUEST, FLAGS, query(
            filter=[{"column": "team", "op": "eq", "value": "b"}, {"column": "score", "op": "valid"}],
            aggregates=[{"name": "rows", "fn": "count"}, {"name": "present", "fn": "count_values", "column": "hours"},
                        {"name": "mean", "fn": "mean", "column": "hours"}, {"name": "median", "fn": "median", "column": "score"},
                        {"name": "low", "fn": "min", "column": "score"}, {"name": "high", "fn": "max", "column": "score"}]))
        self.assertEqual(out["result"], [{"rows": 2, "present": 1, "mean": 4.0, "median": 35.0, "low": 30, "high": 40}])

    def test_halves_round_to_even(self) -> None:
        table = read_csv(b"team,score,hours\r\na,1,0.125\r\na,1,0.125\r\n")
        out = run_query(table, REQUEST, flag(table, REQUEST), query(aggregates=[{"name": "m", "fn": "mean", "column": "hours"}]))
        self.assertEqual(out["result"], [{"m": 0.12}])

    def test_a_numeric_aggregate_over_text_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            run_query(TABLE, REQUEST, FLAGS, query(aggregates=[{"name": "t", "fn": "sum", "column": "score"}]))
        with self.assertRaises(ValueError):
            run_query(TABLE, REQUEST, FLAGS, query(aggregates=[{"name": "t", "fn": "mean", "column": "team"}]))

    def test_outlier_and_comparison_filters(self) -> None:
        flagged = next(o for o in FLAGS["outliers"] if o["column"] == "score")
        self.assertEqual(flagged["rows"], [6])
        out = run_query(TABLE, REQUEST, FLAGS, query(
            filter=[{"column": "score", "op": "valid"}, {"column": "score", "op": "not_outlier"}, {"column": "score", "op": "ge", "value": 20}],
            aggregates=[{"name": "n", "fn": "count"}]))
        self.assertEqual(out["result"], [{"n": 5}])
        inside = run_query(TABLE, REQUEST, FLAGS, query(filter=[{"column": "team", "op": "in", "value": ["c"]}],
                                                        aggregates=[{"name": "n", "fn": "count"}]))
        self.assertEqual(inside["result"], [{"n": 1}])

    def test_digests_are_reproducible_and_change_with_the_query(self) -> None:
        q = query(aggregates=[{"name": "n", "fn": "count"}])
        first, second = run_query(TABLE, REQUEST, FLAGS, q), run_query(TABLE, REQUEST, FLAGS, q)
        self.assertEqual(first, second)
        self.assertEqual(first["result_sha256"], digest(first["result"]))
        self.assertEqual(first["query_sha256"], digest(q))
        other = run_query(TABLE, REQUEST, FLAGS, {**q, "group_by": ["team"]})
        self.assertNotEqual(other["query_sha256"], first["query_sha256"])

    def test_bad_queries_are_refused(self) -> None:
        for bad in (query(filter=[{"column": "team", "op": "like", "value": "a"}], aggregates=[{"name": "n", "fn": "count"}]),
                    query(filter=[{"column": "nope", "op": "valid"}], aggregates=[{"name": "n", "fn": "count"}]),
                    query(aggregates=[{"name": "n", "fn": "mode", "column": "score"}])):
            with self.subTest(query=bad), self.assertRaises(ValueError):
                run_query(TABLE, REQUEST, FLAGS, bad)
        with self.assertRaises(ValueError):
            run_queries(TABLE, REQUEST, FLAGS, [query(aggregates=[{"name": "n", "fn": "count"}])] * 2)


if __name__ == "__main__":
    unittest.main()
