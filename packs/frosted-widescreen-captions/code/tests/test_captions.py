import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from frosted_captions import Cue, ZeroHardcodedValuesAstGate, band_svg, check, pill_box, split_cues, visible_spans, wrap_balanced  # noqa: E402
from frosted_captions.geometry import BAND_Y, CENTER, FRAME, clear_of, inside_band  # noqa: E402


class Wrap(unittest.TestCase):
    def test_one_line_when_it_fits(self):
        self.assertEqual(wrap_balanced("Nonprofits say what they need."), ["Nonprofits say what they need."])

    def test_clause_break_beats_pure_balance(self):
        self.assertEqual(wrap_balanced("Nonprofits say what they need, in plain words."),
                         ["Nonprofits say what they need,", "in plain words."])

    def test_sentence_break(self):
        self.assertEqual(wrap_balanced("Their real sheet never leaves them. Volunteers build it with made-up rows."),
                         ["Their real sheet never leaves them.", "Volunteers build it with made-up rows."])

    def test_protected_name_is_not_split(self):
        lines = wrap_balanced("On our example tests, tuning lifted Muse Glimmer from 93 to 99 percent.")
        self.assertEqual(lines, ["On our example tests, tuning lifted", "Muse Glimmer from 93 to 99 percent."])

    def test_never_ends_on_article_or_preposition(self):
        bad = {"a", "an", "the", "of", "to", "and", "with", "for"}
        for t in ["Only one agent works on it at a time, and every step is recorded.",
                  "A volunteer's AI picks it up, with tokens they weren't going to use.",
                  "Tessera keeps the queue and the nouns, and Herma brings the right ones."]:
            lines = wrap_balanced(t)
            self.assertLessEqual(len(lines), 2)
            for ln in lines:
                self.assertLessEqual(len(ln), 42)
            self.assertNotIn(lines[0].split()[-1].lower().strip(",."), bad, lines)

    def test_no_orphan(self):
        lines = wrap_balanced("A different volunteer's agent reviews it carefully today.")
        self.assertGreaterEqual(min(map(len, lines)) / max(map(len, lines)), 0.4)

    def test_overlong_comes_back_for_the_checker(self):
        t = "x" * 50
        self.assertEqual(wrap_balanced(t), [t])


class SplitCues(unittest.TestCase):
    def test_long_line_splits_at_clause(self):
        t = "This film was assembled from nouns and verbs, claimed and finished by workers on Tessera, with a receipt for every step."
        parts = split_cues(t)
        self.assertGreater(len(parts), 1)
        self.assertEqual(" ".join(parts), t)
        for p in parts:
            lines = wrap_balanced(p)
            self.assertLessEqual(len(lines), 2)
            self.assertTrue(all(len(x) <= 42 for x in lines))

    def test_short_line_stays_whole(self):
        self.assertEqual(split_cues("Spare tokens, for good."), ["Spare tokens, for good."])


class Timing(unittest.TestCase):
    def test_bridges_small_gaps(self):
        cues = [Cue(1.0, 3.0, "They press Send."), Cue(3.3, 5.5, "The request gets its own page.")]
        spans = visible_spans(cues)
        self.assertAlmostEqual(spans[0][1], 3.3 - 2 / 30, places=3)

    def test_large_gap_lingers_six_frames(self):
        cues = [Cue(1.0, 3.0, "They press Send."), Cue(5.0, 7.0, "Then it waits in line.")]
        self.assertAlmostEqual(visible_spans(cues)[0][1], 3.0 + 6 / 30, places=3)

    def test_reading_budget_is_enforced(self):
        fast = [Cue(0.0, 1.2, "A different volunteer's agent reviews it carefully today.")]
        self.assertTrue(any(sev == "error" and "reading" in msg for sev, _, msg in check(fast, film_end=20)))
        ok = [Cue(0.0, 3.6, "A different volunteer's agent reviews it.")]
        self.assertFalse([p for p in check(ok, film_end=20) if p[0] == "error"])


class Geometry(unittest.TestCase):
    def test_contract_numbers(self):
        self.assertEqual(CENTER, (960, 1002))
        self.assertEqual(BAND_Y, (924, 1080))
        self.assertEqual(FRAME["pacing"]["min_shot_s"], 1.8)

    def test_two_line_pill_keeps_24px_from_band_edges(self):
        box = pill_box(["Their real sheet never leaves them.", "Volunteers build it with made-up rows."])
        self.assertTrue(inside_band(box))
        self.assertAlmostEqual(box[1] + box[3] / 2, 1002)
        self.assertAlmostEqual(box[3], 108)

    def test_guide_figure_clearance(self):
        box = pill_box(["A volunteer's AI picks it up,", "with tokens they weren't going to use."])
        guide = (48, 932, 120, 140)
        self.assertTrue(clear_of(box, [guide]))


class Render(unittest.TestCase):
    def test_svg_is_deterministic_and_escaped(self):
        a, b = band_svg("Tom & Jerry's “pantry”"), band_svg("Tom & Jerry's “pantry”")
        self.assertEqual(a, b)
        self.assertIn("&amp;", a)
        self.assertIn('rx="18"', a)
        self.assertIn('height="156"', a)

    def test_zero_hardcoded_values_ast_gate(self):
        here = pathlib.Path(__file__).resolve().parent.parent
        res = ZeroHardcodedValuesAstGate.scan_paths(sorted((here / "frosted_captions").glob("*.py")))
        self.assertEqual(res["violation_count"], 0, res["violations"])


if __name__ == "__main__":
    unittest.main()
