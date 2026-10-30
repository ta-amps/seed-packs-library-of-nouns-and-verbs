"""Caption cues: wrapping, splitting, pause snapping, timing rules and the WebVTT and SRT text."""

from __future__ import annotations

import unittest

from explainer_checks.captions import (build_cues, check_cues, pieces, split_long, stamp, to_srt, to_webvtt,
                                       wrap)


def placement(text: str, speech: list[float], pauses: list[list[float]], line: str = "l1") -> dict:
    return {"line": line, "beat_id": "b", "text": text, "speech_s": speech, "pauses_s": pauses}


class Wrapping(unittest.TestCase):
    def test_short_text_stays_on_one_line(self) -> None:
        self.assertEqual(wrap("They log what is running low."), ["They log what is running low."])

    def test_long_text_splits_into_the_most_even_two_lines(self) -> None:
        self.assertEqual(wrap("Every evening, volunteers check the Velmora Street fridge."),
                         ["Every evening, volunteers check", "the Velmora Street fridge."])

    def test_text_that_two_lines_cannot_hold_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            wrap("x" * 43)
        with self.assertRaises(ValueError):
            wrap(" ".join(["word"] * 20))


class Splitting(unittest.TestCase):
    def test_a_sentence_that_fits_is_kept_whole(self) -> None:
        self.assertEqual(split_long("An AI drafts the restock list overnight."), ["An AI drafts the restock list overnight."])

    def test_a_long_sentence_splits_at_the_comma_nearest_its_middle(self) -> None:
        text = "An AI drafts the restock list overnight, and by morning a person signs off on every change."
        self.assertEqual(split_long(text), ["An AI drafts the restock list overnight,",
                                            "and by morning a person signs off on every change."])

    def test_a_long_sentence_without_a_comma_splits_at_its_middle_word(self) -> None:
        text = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"
        parts = split_long(text)
        self.assertEqual(" ".join(parts), text)
        self.assertGreater(len(parts), 1)

    def test_one_unsplittable_word_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            split_long("y" * 90)


class Pieces(unittest.TestCase):
    def test_splits_snap_to_the_nearest_unused_pause(self) -> None:
        text = "Every evening, volunteers check the Velmora Street fridge. They log what is running low."
        got = pieces(text, [550, 6310], [[1330, 1550], [4120, 4500]])
        self.assertEqual([(p["start_ms"], p["end_ms"]) for p in got], [(550, 4120), (4500, 6310)])

    def test_without_a_pause_nearby_the_estimate_is_used(self) -> None:
        got = pieces("First part here. Second part here.", [0, 4000], [[3900, 3950]])
        self.assertEqual(got[0]["end_ms"], got[1]["start_ms"])
        self.assertEqual(got[0]["end_ms"], 4000 * 16 // 33)


class Cues(unittest.TestCase):
    def test_cues_follow_every_rule_and_close_blink_gaps(self) -> None:
        text = "An AI drafts the restock list overnight, and by morning a person signs off on every change."
        cues = build_cues([placement(text, [10.25, 16.77], [[13.15, 13.45]], "l2")], 20.0, 30)
        self.assertEqual([(c["start_frame"], c["end_frame"]) for c in cues], [(308, 404), (404, 511)])
        self.assertEqual(cues[1]["lines"], ["and by morning a person", "signs off on every change."])
        self.assertEqual(check_cues(cues, 30), [])

    def test_the_last_cue_stops_before_the_cut_ends_and_short_cues_last_a_second(self) -> None:
        cues = build_cues([placement("Hi.", [19.0, 19.2], [])], 20.0, 30)
        self.assertEqual(cues[0]["end_frame"], 599)
        cues = build_cues([placement("Hi.", [1.0, 1.2], [])], 20.0, 30)
        self.assertEqual(cues[0]["end_frame"] - cues[0]["start_frame"], 30)

    def test_each_rule_break_is_named(self) -> None:
        good = {"cue_id": "c01", "start_frame": 0, "end_frame": 60, "text": "Short and fine.", "lines": ["Short and fine."]}
        cases = {
            "outside 1000 to 7000 ms": [{**good, "end_frame": 20}],
            "faster than 17": [{**good, "text": "x " * 20, "lines": wrap(("x " * 20).strip()), "end_frame": 30}],
            "ends before it starts": [{**good, "end_frame": 0}],
            "overlaps": [good, {**good, "cue_id": "c02", "start_frame": 50, "end_frame": 120}],
            "gap of under 3 frames": [good, {**good, "cue_id": "c02", "start_frame": 62, "end_frame": 120}],
            "balanced wrap": [{**good, "lines": ["Short and", "fine."]}],
            "does not fit": [{**good, "text": "z" * 50, "lines": ["z" * 50]}],
        }
        for words, cues in cases.items():
            with self.subTest(words=words):
                self.assertTrue(any(words in p for p in check_cues(cues, 30)), check_cues(cues, 30))


class Sidecars(unittest.TestCase):
    CUES = [{"start_frame": 17, "end_frame": 131, "lines": ["Every evening, volunteers check", "the Velmora Street fridge."]},
            {"start_frame": 135, "end_frame": 197, "lines": ["They log what is running low."]}]

    def test_timestamps(self) -> None:
        self.assertEqual(stamp(17, 30, "."), "00:00:00.567")
        self.assertEqual(stamp(30 * 3725 + 3, 30, ","), "01:02:05,100")

    def test_webvtt_text_is_exact(self) -> None:
        self.assertEqual(to_webvtt(self.CUES, 30),
                         "WEBVTT\n\n00:00:00.567 --> 00:00:04.367\nEvery evening, volunteers check\n"
                         "the Velmora Street fridge.\n\n00:00:04.500 --> 00:00:06.567\nThey log what is running low.\n")

    def test_srt_text_is_exact(self) -> None:
        self.assertEqual(to_srt(self.CUES, 30),
                         "1\n00:00:00,567 --> 00:00:04,367\nEvery evening, volunteers check\nthe Velmora Street fridge.\n"
                         "\n2\n00:00:04,500 --> 00:00:06,567\nThey log what is running low.\n")


if __name__ == "__main__":
    unittest.main()
