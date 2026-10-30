"""Each text case holds what its label says, measured with the standard library's Unicode data."""

from __future__ import annotations

import unicodedata
import unittest

from edge_cases import generate


def by_label(**limits) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for case in generate(["strings"], 20261030, {"strings": limits} if limits else None)["cases"]:
        out.setdefault(case["label"], []).append(case)
    return out


CASES = by_label()


def value(label: str) -> str:
    return CASES[label][0]["value"]


class Sizes(unittest.TestCase):
    def test_sizes_follow_the_length_limit(self) -> None:
        cases = by_label(max_length=10)
        self.assertEqual(len(cases["strings.size.at-max"][0]["value"]), 10)
        self.assertEqual(len(cases["strings.size.over-max"][0]["value"]), 11)
        self.assertEqual(len(cases["strings.size.huge"][0]["value"]), 640)

    def test_three_lengths_are_reported(self) -> None:
        emoji = CASES["strings.unicode.emoji"][0]
        self.assertEqual(emoji["size"], {"code_points": 1, "utf8_bytes": 4, "utf16_units": 2})
        family = CASES["strings.unicode.emoji-zwj-family"][0]
        self.assertEqual(family["size"]["code_points"], 5)
        self.assertEqual(family["size"]["utf16_units"], 8)

    def test_long_values_have_no_space_to_break_at(self) -> None:
        for label in ("strings.size.long-word", "strings.size.long-token"):
            self.assertNotIn(" ", value(label))
            self.assertGreaterEqual(len(value(label)), 45, label)


class Unicode(unittest.TestCase):
    def test_composed_and_decomposed_names_differ_until_normalized(self) -> None:
        decomposed, composed = value("strings.unicode.combining-mark"), value("strings.unicode.precomposed")
        self.assertNotEqual(decomposed, composed)
        self.assertEqual(unicodedata.normalize("NFC", decomposed), composed)
        self.assertEqual(unicodedata.combining(decomposed[-1]), 230)

    def test_stacked_marks_are_one_base_and_eight_marks(self) -> None:
        text = value("strings.unicode.stacked-marks")
        self.assertEqual(sum(1 for ch in text if unicodedata.combining(ch)), 8)
        self.assertEqual(len(text), 9)

    def test_right_to_left_cases_hold_strong_right_to_left_letters(self) -> None:
        for label in ("strings.unicode.rtl-arabic", "strings.unicode.rtl-hebrew", "strings.unicode.rtl-with-digits"):
            self.assertTrue(any(unicodedata.bidirectional(ch) in ("R", "AL") for ch in value(label)), label)
        mixed = value("strings.unicode.rtl-with-digits")
        self.assertTrue(any(unicodedata.bidirectional(ch) == "EN" for ch in mixed))
        self.assertTrue(any(unicodedata.bidirectional(ch) == "L" for ch in mixed))
        self.assertIn("\u202e", value("strings.unicode.bidi-override"))
        self.assertEqual(unicodedata.bidirectional("\u202e"), "RLO")

    def test_invisible_characters_are_where_the_labels_say(self) -> None:
        for label, char, category in (("strings.zero-width.space", "\u200b", "Cf"),
                                      ("strings.zero-width.joiner", "\u200d", "Cf"),
                                      ("strings.zero-width.non-joiner", "\u200c", "Cf"),
                                      ("strings.zero-width.byte-order-mark", "\ufeff", "Cf"),
                                      ("strings.zero-width.word-joiner", "\u2060", "Cf")):
            self.assertIn(char, value(label), label)
            self.assertEqual(unicodedata.category(char), category, label)

    def test_emoji_sequences_are_built_from_their_parts(self) -> None:
        self.assertGreater(ord(value("strings.unicode.emoji")), 0xFFFF)
        self.assertEqual(value("strings.unicode.emoji-zwj-family").count("\u200d"), 2)
        self.assertEqual(unicodedata.name(value("strings.unicode.emoji-skin-tone")[1]), "EMOJI MODIFIER FITZPATRICK TYPE-4")
        self.assertTrue(all(unicodedata.name(ch).startswith("REGIONAL INDICATOR SYMBOL LETTER")
                            for ch in value("strings.unicode.flag")))
        self.assertEqual(unicodedata.name(value("strings.unicode.keycap")[-1]), "COMBINING ENCLOSING KEYCAP")

    def test_lookalikes_and_compatibility_forms(self) -> None:
        confusable = value("strings.unicode.confusable")
        self.assertNotEqual(confusable, "admin")
        self.assertEqual(unicodedata.name(confusable[0]), "CYRILLIC SMALL LETTER A")
        self.assertEqual(unicodedata.normalize("NFKC", value("strings.unicode.fullwidth")), "ABC123")
        self.assertEqual(unicodedata.normalize("NFKC", value("strings.unicode.ligature")), "file")

    def test_case_mapping_changes_length(self) -> None:
        sharp = value("strings.unicode.sharp-s")
        self.assertEqual(sharp.upper(), "STRASSE")
        self.assertEqual(sharp.casefold(), "strasse")
        dotted = value("strings.unicode.dotted-capital-i")
        self.assertEqual(len(dotted.lower()), len(dotted) + 1)
        self.assertGreater(ord(value("strings.unicode.non-bmp-ideograph")), 0xFFFF)


class ControlAndMarkup(unittest.TestCase):
    def test_control_characters(self) -> None:
        self.assertIn("\n", value("strings.control.newline"))
        self.assertIn("\r\n", value("strings.control.crlf"))
        self.assertIn("\t", value("strings.control.tab"))
        self.assertIn("\u0000", value("strings.control.nul"))
        self.assertEqual(unicodedata.category(value("strings.control.line-separator")[1]), "Zl")

    def test_markup_shapes(self) -> None:
        self.assertTrue(value("strings.markup.spreadsheet-formula").startswith("="))
        self.assertIn("../", value("strings.markup.path-like"))
        self.assertIn("{{", value("strings.markup.template-braces"))
        self.assertIn("<", value("strings.markup.angle-brackets"))

    def test_empty_and_whitespace(self) -> None:
        self.assertEqual(value("strings.empty"), "")
        self.assertEqual(value("strings.whitespace.only").strip(), "")
        self.assertEqual(value("strings.whitespace.no-break-space"), "\u00a0")
        self.assertEqual(value("strings.whitespace.no-break-space").strip(), "", "str.strip removes it; many trims do not")
        self.assertNotEqual(value("strings.whitespace.padded"), value("strings.whitespace.padded").strip())


class Seeded(unittest.TestCase):
    def test_seeded_text_is_reproducible_and_seed_dependent(self) -> None:
        one = [c["value"] for c in CASES["strings.seeded.mixed"]]
        again = [c["value"] for c in by_label()["strings.seeded.mixed"]]
        other = [c["value"] for c in generate(["strings"], 1)["cases"] if c["label"] == "strings.seeded.mixed"]
        self.assertEqual(one, again)
        self.assertNotEqual(one, other)
        self.assertEqual(len(one), 3)
        none = [c for c in generate(["strings"], 1, {"strings": {"seeded": 0}})["cases"] if c["group"] == "seeded"]
        self.assertEqual(none, [])


if __name__ == "__main__":
    unittest.main()
