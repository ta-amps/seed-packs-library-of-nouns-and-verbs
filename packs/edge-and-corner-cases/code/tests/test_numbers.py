"""Each number case holds what its label says: limits, exactness in a double, and text parsers disagree on."""

from __future__ import annotations

import math
import unicodedata
import unittest

from edge_cases import generate


def cases(**limits) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for case in generate(["numbers"], 20261030, {"numbers": limits} if limits else None)["cases"]:
        out.setdefault(case["label"], []).append(case)
    return out


CASES = cases()


def value(label: str) -> str:
    return CASES[label][0]["value"]


class Boundaries(unittest.TestCase):
    def test_limits_and_one_step_past_them(self) -> None:
        got = cases(minimum=1, maximum=50)
        self.assertEqual([got[f"numbers.boundary.{name}"][0]["value"] for name in
                          ("minimum", "below-minimum", "maximum", "above-maximum")], ["1", "0", "50", "51"])
        self.assertEqual(got["numbers.boundary.minimum"][0]["context"], {"minimum": 1, "maximum": 50})

    def test_minimum_above_maximum_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            generate(["numbers"], 1, {"numbers": {"minimum": 5, "maximum": 4}})

    def test_seeded_values_sit_within_two_of_a_limit(self) -> None:
        got = cases(minimum=10, maximum=20, seeded=20)
        for case in got["numbers.seeded.near-boundary"]:
            n = int(case["value"])
            self.assertTrue(min(abs(n - 10), abs(n - 20)) <= 2, n)


class Exactness(unittest.TestCase):
    def test_doubles_hold_the_safe_integers_and_lose_the_next_odd_one(self) -> None:
        self.assertEqual(int(float(value("numbers.integer.max-safe"))), 2**53 - 1)
        self.assertEqual(int(float(value("numbers.integer.max-safe-plus-one"))), 2**53)
        self.assertNotEqual(int(float(value("numbers.integer.max-safe-plus-two"))), 2**53 + 1)
        self.assertEqual(float(2**53), float(2**53 + 1), "a double cannot tell 2**53 from 2**53 + 1")
        self.assertNotEqual(float(2**53 - 1), float(2**53), "but 2**53 - 1 and 2**53 are both exact")

    def test_integer_widths(self) -> None:
        self.assertEqual(int(value("numbers.integer.int32-overflow")), 2**31)
        self.assertEqual(int(value("numbers.integer.int64-overflow")), 2**63)

    def test_floating_point_edges(self) -> None:
        self.assertNotEqual(float(value("numbers.float.one-tenth")) * 3, 0.3)
        self.assertEqual(float(value("numbers.float.smallest-subnormal")), 5e-324)
        self.assertGreater(float(value("numbers.float.smallest-subnormal")), 0)
        self.assertTrue(math.isfinite(float(value("numbers.float.largest"))))
        self.assertTrue(math.isinf(float(value("numbers.float.overflow"))), "Python turns it into infinity")
        self.assertNotEqual(repr(float(value("numbers.float.many-digits"))), value("numbers.float.many-digits"))

    def test_words_a_parser_may_accept(self) -> None:
        self.assertTrue(math.isnan(float(value("numbers.word.nan"))), "Python's float accepts it, which is the point")
        self.assertTrue(math.isinf(float(value("numbers.word.infinity"))))
        self.assertEqual(float(value("numbers.sign.negative-zero")), 0.0)
        self.assertEqual(math.copysign(1, float(value("numbers.sign.negative-zero"))), -1.0)


class Formats(unittest.TestCase):
    def test_grouping_marks_are_the_ones_named(self) -> None:
        self.assertIn("\u202f", value("numbers.format.narrow-space-group"))
        self.assertEqual(unicodedata.name("\u202f"), "NARROW NO-BREAK SPACE")
        self.assertEqual(CASES["numbers.format.decimal-comma"][0]["context"], {"locale_hint": "de-DE"})

    def test_digits_from_other_scripts_read_as_the_same_digits(self) -> None:
        for label in ("numbers.format.arabic-indic-digits", "numbers.format.fullwidth-digits"):
            self.assertEqual("".join(str(unicodedata.digit(ch)) for ch in value(label)), "123", label)
            self.assertEqual(int(value(label)), 123, "Python's int accepts them; many parsers do not")

    def test_the_minus_sign_is_not_a_hyphen(self) -> None:
        self.assertEqual(unicodedata.name(value("numbers.format.unicode-minus")[0]), "MINUS SIGN")
        with self.assertRaises(ValueError):
            int(value("numbers.format.unicode-minus"))

    def test_text_that_strict_integer_parsing_refuses(self) -> None:
        for label in ("numbers.format.thousands-comma", "numbers.format.hex", "numbers.format.currency",
                      "numbers.format.percent", "numbers.format.fraction", "numbers.format.trailing-point"):
            with self.subTest(label=label), self.assertRaises(ValueError):
                int(value(label))
        self.assertEqual(int(value("numbers.format.leading-zeros")), 7)
        self.assertEqual(int(value("numbers.format.surrounding-spaces")), 42, "Python trims; strict parsers do not")


if __name__ == "__main__":
    unittest.main()
