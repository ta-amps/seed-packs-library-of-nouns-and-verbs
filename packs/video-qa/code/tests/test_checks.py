"""Picture and sound rows: declared holds, pauses and black are honored; everything else is reported."""

from __future__ import annotations

import unittest

from video_qa_checks.checks import (check_blank, check_cadence, check_clipping, check_frozen, check_loudness,
                                    check_silence, inside, runs)

PLAN = {"duration_s": 12.0, "fps": 30, "holds": [[9.0, 10.5, "end card"]], "pauses": [[6.0, 6.8, "breath"]],
        "black": [[11.5, 12.0, "fade out"]]}


def frames(values: list[float], fps: int = 30, start: float = 0.0) -> list[tuple[float, float]]:
    return [(round(start + i / fps, 6), v) for i, v in enumerate(values)]


class Spans(unittest.TestCase):
    def test_inside_with_a_tail(self) -> None:
        self.assertTrue(inside(9.2, 10.4, PLAN["holds"]))
        self.assertFalse(inside(9.2, 11.0, PLAN["holds"]))
        self.assertTrue(inside(9.2, 11.0, PLAN["holds"], tail=0.75))

    def test_runs_end_at_the_next_sample(self) -> None:
        series = [(0.0, 1.0), (0.5, 0.0), (1.0, 0.0), (1.5, 1.0), (2.0, 0.0)]
        self.assertEqual(runs(series, lambda v: v == 0.0, 0.5), [(0.5, 1.5), (2.0, 2.5)])


class Picture(unittest.TestCase):
    def test_black_inside_the_plan_passes_and_a_flash_outside_fails(self) -> None:
        black = [{"start_s": 11.5, "end_s": 12.0, "duration_s": 0.5}, {"start_s": 4.0, "end_s": 4.6, "duration_s": 0.6}]
        result = check_blank(black, [], [], PLAN)
        self.assertEqual(result["result"], "fail")
        self.assertEqual([(f["start_s"], f["what"]) for f in result["findings"]], [(4.0, "black")])

    def test_a_flat_white_frame_is_found_from_luma_range(self) -> None:
        ymin = frames([20, 20, 235, 20])
        ymax = frames([230, 230, 240, 230])
        result = check_blank([], ymin, ymax, PLAN)
        self.assertEqual(result["result"], "warn")
        self.assertEqual(result["findings"][0]["what"], "flat frame")
        self.assertEqual(result["measured"]["smallest_luma_range"], 5)

    def test_frozen_warn_fail_and_holds(self) -> None:
        freezes = [{"start_s": 1.0, "end_s": 2.6, "duration_s": 1.6}, {"start_s": 3.0, "end_s": 5.5, "duration_s": 2.5},
                   {"start_s": 9.0, "end_s": 11.1, "duration_s": 2.1}, {"start_s": 7.0, "end_s": 8.0, "duration_s": 1.0}]
        result = check_frozen(freezes, PLAN)
        self.assertEqual(result["result"], "fail")
        self.assertEqual([(f["start_s"], f["severity"]) for f in result["findings"]], [(1.0, "warn"), (3.0, "fail")])
        self.assertEqual(result["measured"]["longest_s"], 2.5)

    def test_cadence_cuts_shots_and_still_stretches(self) -> None:
        scores = [(t / 2, 0.01) for t in range(24)]
        scores[4] = (2.0, 0.3)
        for i in range(10, 19):
            scores[i] = (i / 2, 0.0005)
        result = check_cadence(scores, PLAN)
        self.assertEqual(result["measured"]["cuts"], [2.0])
        self.assertEqual(result["measured"]["longest_shot_s"], 10.0)
        self.assertEqual(result["result"], "warn")
        self.assertEqual([(f["start_s"], f["end_s"]) for f in result["findings"]], [(5.0, 9.5)])
        self.assertEqual(check_cadence([], PLAN)["result"], "not_run")

    def test_a_still_inside_a_hold_is_not_reported(self) -> None:
        scores = [(t / 2, 0.01) for t in range(24)]
        for i in range(18, 21):
            scores[i] = (i / 2, 0.0)
        self.assertEqual(check_cadence(scores, PLAN, {"still_warn_s": 1.0})["findings"], [])


class Sound(unittest.TestCase):
    def test_loudness_passes_inside_tolerance(self) -> None:
        summary = {"integrated_lufs": -16.4, "lra_lu": 4.0, "true_peak_dbtp": -1.5}
        result = check_loudness(summary, [{"t_s": 5.0, "momentary_lufs": -18, "short_term_lufs": -19}], PLAN)
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["measured"]["quietest_short_term_lufs"], -19)

    def test_loudness_failures_and_warnings(self) -> None:
        summary = {"integrated_lufs": -12.0, "lra_lu": 12.5, "true_peak_dbtp": -0.2}
        quiet = [{"t_s": 5.0, "momentary_lufs": -40, "short_term_lufs": -31}]
        result = check_loudness(summary, quiet, PLAN)
        self.assertEqual(result["result"], "fail")
        self.assertEqual([f["severity"] for f in result["findings"]], ["fail", "fail", "warn", "warn"])
        self.assertEqual(check_loudness({"integrated_lufs": None}, [], PLAN)["result"], "not_run")

    def test_a_quiet_window_inside_a_declared_pause_is_allowed(self) -> None:
        summary = {"integrated_lufs": -16.0, "lra_lu": 3.0, "true_peak_dbtp": -2.0}
        quiet = [{"t_s": 6.8, "momentary_lufs": -40, "short_term_lufs": -30}]
        plan = {**PLAN, "pauses": [[3.8, 6.8, "long pause"]]}
        self.assertEqual(check_loudness(summary, quiet, plan)["result"], "pass")

    def test_silence_gaps(self) -> None:
        silences = [{"start_s": 6.1, "end_s": 6.7, "duration_s": 0.6}, {"start_s": 2.0, "end_s": 2.7, "duration_s": 0.7},
                    {"start_s": 7.0, "end_s": 9.5, "duration_s": 2.5}, {"start_s": 1.0, "end_s": 1.3, "duration_s": 0.3}]
        result = check_silence(silences, PLAN)
        self.assertEqual([(f["start_s"], f["severity"]) for f in result["findings"]], [(2.0, "warn"), (7.0, "fail")])

    def test_clipping(self) -> None:
        clipped = {"peak_level_db": 0.000265, "peak_count": 31760.0, "flat_factor": 31.148508}
        clean = {"peak_level_db": -1.30229, "peak_count": 2.0, "flat_factor": 0.0}
        self.assertEqual(check_clipping(clipped)["result"], "fail")
        self.assertEqual(check_clipping(clean)["result"], "pass")
        self.assertEqual(check_clipping({"peak_level_db": None})["result"], "not_run")

    def test_unknown_limits_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            check_clipping({"peak_level_db": 0.0}, {"clip_peak": 1})


if __name__ == "__main__":
    unittest.main()
