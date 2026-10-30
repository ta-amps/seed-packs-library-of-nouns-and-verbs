"""Each body case does what its label says to a strict JSON parser, and Python's lenient defaults are shown
for contrast: the lenient behavior is the edge."""

from __future__ import annotations

import json
import math
import unittest

from edge_cases import generate
from edge_cases.bodies import BASE


def strict_loads(text: str):
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate key")
        return dict(items)

    def constant(name):
        raise ValueError(f"non-standard constant {name}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def cases(**limits) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for case in generate(["bodies"], 20261030, {"bodies": limits} if limits else None)["cases"]:
        out.setdefault(case["label"], []).append(case)
    return out


CASES = cases()


def value(label: str) -> str:
    return CASES[label][0]["value"]


class Bodies(unittest.TestCase):
    def test_the_control_parses(self) -> None:
        self.assertEqual(strict_loads(value("bodies.valid.minimal")), {"name": "Test Volunteer", "spots": 2})

    def test_syntax_cases_fail_a_strict_parser(self) -> None:
        for label in ("bodies.syntax.truncated", "bodies.syntax.trailing-comma", "bodies.syntax.single-quotes",
                      "bodies.syntax.comment", "bodies.syntax.nan-token", "bodies.syntax.byte-order-mark",
                      "bodies.syntax.empty", "bodies.syntax.whitespace-only", "bodies.semantics.duplicate-keys"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                strict_loads(value(label))

    def test_what_a_lenient_parser_does_instead(self) -> None:
        self.assertEqual(json.loads(value("bodies.semantics.duplicate-keys"))["name"], "Other Volunteer", "the last one wins")
        self.assertTrue(math.isnan(json.loads(value("bodies.syntax.nan-token"))["spots"]), "Python accepts NaN by default")
        big = json.loads(value("bodies.semantics.big-integer"))["spots"]
        self.assertEqual(big, 2**53 + 1)
        self.assertNotEqual(float(big), big, "a double changes it")

    def test_valid_syntax_that_a_schema_must_refuse(self) -> None:
        self.assertIsNone(strict_loads(value("bodies.semantics.null-required"))["name"])
        self.assertIsInstance(strict_loads(value("bodies.semantics.wrong-type"))["name"], int)
        self.assertIsInstance(strict_loads(value("bodies.semantics.top-level-array")), list)
        self.assertIsNone(strict_loads(value("bodies.semantics.top-level-null")))
        self.assertIn("nickname", strict_loads(value("bodies.semantics.unknown-field")))
        lone = strict_loads(value("bodies.semantics.lone-surrogate-escape"))["name"]
        with self.assertRaises(UnicodeEncodeError):
            lone.encode("utf-8")
        self.assertEqual(strict_loads(value("bodies.encoding.escaped-unicode"))["name"], "Jos\u00e9")

    def test_sizes_follow_the_limits(self) -> None:
        got = cases(max_bytes=100, depth=5)
        over = got["bodies.size.over-limit"][0]
        self.assertEqual(len(over["value"].encode("utf-8")), 101)
        self.assertEqual(over["context"]["max_bytes"], 100)
        self.assertEqual(strict_loads(got["bodies.size.deep-nesting"][0]["value"]), [[[[[[]]]]]], "one level past the limit of 5")
        self.assertEqual(got["bodies.size.deep-nesting"][0]["context"]["max_depth"], 5)
        with self.assertRaises(RecursionError):
            json.loads(cases(depth=100000)["bodies.size.deep-nesting"][0]["value"])

    def test_headers_vary_and_the_body_does_not(self) -> None:
        for label in ("bodies.header.text-plain", "bodies.header.form-encoded", "bodies.header.missing", "bodies.header.wrong-charset"):
            self.assertEqual(value(label), BASE, label)
        self.assertIsNone(CASES["bodies.header.missing"][0]["context"]["content_type"])

    def test_seeded_mutations_change_exactly_one_character(self) -> None:
        for case in cases(seeded=20)["bodies.seeded.mutated"]:
            text, how = case["value"], case["context"]
            self.assertEqual(len(text) - len(BASE), {"insert": 1, "delete": -1, "replace": 0}[how["mutation"]], how)
            if how["mutation"] == "delete":
                self.assertEqual(text, BASE[:how["at"]] + BASE[how["at"] + 1:])
            else:
                self.assertEqual(text[how["at"]], how["char"])


if __name__ == "__main__":
    unittest.main()
