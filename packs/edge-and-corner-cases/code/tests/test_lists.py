"""Each list case holds what its label says: page sizes, duplicates in disguise and orders that trip sorting."""

from __future__ import annotations

import unicodedata
import unittest
from collections import Counter

from edge_cases import generate


def cases(**limits) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for case in generate(["lists"], 20261030, {"lists": limits} if limits else None)["cases"]:
        out.setdefault(case["label"], []).append(case)
    return out


class Lists(unittest.TestCase):
    def test_sizes_follow_the_page_size(self) -> None:
        got = cases(page_size=7)
        self.assertEqual(len(got["lists.size.page"][0]["value"]), 7)
        self.assertEqual(len(got["lists.size.page-plus-one"][0]["value"]), 8)
        self.assertEqual(len(got["lists.size.huge"][0]["value"]), 700)
        self.assertEqual(got["lists.size.huge"][0]["size"], {"items": 700})
        self.assertEqual(got["lists.size.empty"][0]["value"], [])

    def test_duplicates_in_disguise(self) -> None:
        got = cases()
        self.assertEqual(len({v.casefold() for v in got["lists.duplicates.case"][0]["value"]}), 1)
        self.assertEqual(len({v.strip() for v in got["lists.duplicates.spacing"][0]["value"]}), 1)
        names = got["lists.duplicates.normalization"][0]["value"]
        self.assertEqual(len(set(names)), 2)
        self.assertEqual(len({unicodedata.normalize("NFC", v) for v in names}), 1)
        records = got["lists.duplicates.same-id"][0]["value"]
        self.assertEqual(len({r["id"] for r in records}), 1)
        self.assertEqual(len({r["name"] for r in records}), 2)

    def test_orders_that_trip_sorting(self) -> None:
        got = cases()
        self.assertEqual(sorted(got["lists.order.numeric-strings"][0]["value"]), ["10", "100", "9"])
        self.assertEqual(sorted(got["lists.order.numeric-strings"][0]["value"], key=int), ["9", "10", "100"])
        stable = sorted(got["lists.order.equal-keys"][0]["value"], key=lambda r: r["key"])
        self.assertEqual([r["id"] for r in stable], ["third", "first", "second"])
        words = got["lists.order.case-and-accents"][0]["value"]
        self.assertEqual(sorted(words)[0], "Banana", "code-point order puts capitals first")
        self.assertEqual(sorted(words)[-1], "\u00e9clair", "and accented letters last")

    def test_seeded_shuffles_keep_their_items(self) -> None:
        got = cases(page_size=9, seeded=5)
        base = Counter(f"item-{i:02d}" for i in range(1, 10))
        for case in got["lists.seeded.shuffled-with-duplicates"]:
            counts = Counter(case["value"])
            self.assertEqual(set(counts), set(base))
            self.assertGreater(sum(counts.values()), 9)


if __name__ == "__main__":
    unittest.main()
