"""Frame clock arithmetic: clip and beat spans, cut checks, narration placement and frame-sheet times."""

from __future__ import annotations

import copy
import unittest

from explainer_checks.clock import (beat_spans, check_cut, check_narration, clip_spans, frame_sheet_times, frames_to_ms,
                                    half_frames_to_ms, ms_to_frame, to_ms, total_frames)

CUT = {
    "cut_id": "20s", "duration_s": 20.0,
    "clips": [
        {"clip_id": "a", "beat_id": "one", "frames": 300, "xfade_frames": 0},
        {"clip_id": "b", "beat_id": "two", "frames": 210, "xfade_frames": 15},
        {"clip_id": "c", "beat_id": "two", "frames": 60, "xfade_frames": 0},
        {"clip_id": "d", "beat_id": "three", "frames": 60, "xfade_frames": 15},
    ],
    "narration": [{"line": "l1", "start_s": 0.5, "beat_id": "one"}, {"line": "l2", "start_s": 10.2, "beat_id": "two"}],
    "claims": [{"claim_id": "n", "beat_id": "one"}],
}
PLACED = [{"line": "l1", "beat_id": "one", "start_s": 0.5, "end_s": 6.36},
          {"line": "l2", "beat_id": "two", "start_s": 10.2, "end_s": 16.82}]


class Rounding(unittest.TestCase):
    def test_milliseconds_and_frames_round_half_up(self) -> None:
        self.assertEqual(to_ms(0.55), 550)
        self.assertEqual(to_ms(13.45), 13450)
        self.assertEqual(ms_to_frame(550, 30), 17)
        self.assertEqual(ms_to_frame(13400, 30), 402)
        self.assertEqual(ms_to_frame(13450, 30), 404)
        self.assertEqual(frames_to_ms(46, 30), 1533)
        self.assertEqual(frames_to_ms(47, 30), 1567)
        self.assertEqual(half_frames_to_ms(585, 30), 9750)
        self.assertEqual(half_frames_to_ms(1, 25), 20)


class Spans(unittest.TestCase):
    def test_clips_start_at_the_previous_end_minus_the_crossfade(self) -> None:
        spans = [(s["clip_id"], s["start_frame"], s["end_frame"]) for s in clip_spans(CUT, 30)]
        self.assertEqual(spans, [("a", 0, 300), ("b", 285, 495), ("c", 495, 555), ("d", 540, 600)])
        self.assertEqual(total_frames(CUT, 30), 600)
        self.assertEqual(total_frames({"clips": []}, 30), 0)

    def test_beats_run_from_mid_crossfade_to_mid_crossfade(self) -> None:
        beats = [(b["beat_id"], b["start_ms"], b["end_ms"]) for b in beat_spans(CUT, 30)]
        self.assertEqual(beats, [("one", 0, 9750), ("two", 9750, 18250), ("three", 18250, 20000)])

    def test_frame_sheet_times_sit_in_the_middle_of_each_solo_span(self) -> None:
        times = [(t["clip_id"], t["time_ms"]) for t in frame_sheet_times(CUT, 30)]
        self.assertEqual(times, [("a", 4750), ("b", 13250), ("c", 17250), ("d", 19250)])


class CutChecks(unittest.TestCase):
    def test_a_clean_cut_has_no_problem(self) -> None:
        self.assertEqual(check_cut(CUT, 30, {"one", "two", "three"}), [])

    def test_each_mistake_is_named(self) -> None:
        cases = {
            "frames, not": lambda c: c["clips"][3].update(frames=58),
            "first clip has no crossfade": lambda c: c["clips"][0].update(xfade_frames=5),
            "crossfade is longer": lambda c: c["clips"][3].update(xfade_frames=61),
            "clip id used twice": lambda c: c["clips"][2].update(clip_id="b"),
            "at least one frame": lambda c: c["clips"].insert(1, {"clip_id": "z", "beat_id": "one", "frames": 0,
                                                                   "xfade_frames": 0}),
            "returns after another beat": lambda c: c["clips"][3].update(beat_id="one"),
            "has no clip in this cut": lambda c: c["narration"][1].update(beat_id="missing"),
        }
        for words, mutate in cases.items():
            cut = copy.deepcopy(CUT)
            mutate(cut)
            with self.subTest(words=words):
                self.assertTrue(any(words in p for p in check_cut(cut, 30)), check_cut(cut, 30))
        cut = copy.deepcopy(CUT)
        cut["claims"][0]["beat_id"] = "missing"
        self.assertTrue(any("n: beat missing" in p for p in check_cut(cut, 30)))
        self.assertTrue(any("not in the cut plan's beats" in p for p in check_cut(CUT, 30, {"one"})))
        self.assertEqual(check_cut({"cut_id": "x", "duration_s": 1, "clips": []}, 30), ["x: no clips"])

    def test_a_duration_between_frames_is_a_problem(self) -> None:
        cut = copy.deepcopy(CUT)
        cut["duration_s"] = 20.01
        self.assertTrue(check_cut(cut, 30))


class Narration(unittest.TestCase):
    def test_placed_lines_that_fit_have_no_problem(self) -> None:
        self.assertEqual(check_narration(CUT, 30, PLACED), [])

    def test_gaps_ends_beats_and_plan_mismatches_are_named(self) -> None:
        def problems(**changes: dict) -> list[str]:
            placed = copy.deepcopy(PLACED)
            for index, change in changes.items():
                placed[int(index[1:])].update(change)
            cut = copy.deepcopy(CUT)
            for item, placement in zip(cut["narration"], placed, strict=True):
                item.update(start_s=placement["start_s"], beat_id=placement["beat_id"])
            return check_narration(cut, 30, placed)

        self.assertTrue(any("under 200 ms" in p for p in problems(i1={"start_s": 6.5, "end_s": 12.0, "beat_id": "one"})))
        self.assertTrue(any("within 100 ms" in p for p in problems(i1={"end_s": 19.95})))
        self.assertTrue(any("outside beat" in p for p in problems(i0={"start_s": 9.9, "end_s": 9.95})))
        self.assertTrue(any("ends before it starts" in p for p in problems(i0={"end_s": 0.4})))
        moved = copy.deepcopy(PLACED)
        moved[1]["start_s"] = 10.3
        self.assertTrue(any("not placed there" in p for p in check_narration(CUT, 30, moved)))
        self.assertTrue(any("does not say" in p for p in check_narration(CUT, 30, moved)))


if __name__ == "__main__":
    unittest.main()
