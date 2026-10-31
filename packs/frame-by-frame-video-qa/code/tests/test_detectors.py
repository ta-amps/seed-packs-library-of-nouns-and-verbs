"""Each detector on hand-built measurement records, with the thresholds of the default spec."""

from __future__ import annotations

import unittest

import numpy as np

from frame_qa.captions import parse_vtt
from frame_qa.detectors import (classify_transitions, detect_caption_collisions, detect_contrast, detect_cut_off_content,
                                detect_cut_off_windows, detect_freezes_and_motion, detect_layered_edges, detect_overlaps,
                                detect_small_text, detect_transitions, lines_of, run_all)

from helpers import context, line, record, spatial_run, temporal


def kinds(hits):
    return sorted({(h.kind, h.severity) for h in hits})


class CutOff(unittest.TestCase):
    def test_edge_action_and_title_margins(self) -> None:
        # 1920 x 1080: action-safe is 67.2 px at the sides, title-safe 96 px.
        texts = [line((0, 300, 300, 330), clipped=("left",)), line((50, 400, 400, 430)), line((80, 500, 400, 530)),
                 line((400, 600, 800, 630))]
        ctx = context([record(0, texts=texts), record(1, spatial=False)])
        hits = detect_cut_off_content(ctx)
        self.assertEqual(kinds(hits), [("text_at_edge", "minor"), ("text_in_action_margin", "minor"), ("text_in_title_margin", "note")])
        edge = next(h for h in hits if h.kind == "text_at_edge")
        self.assertEqual(edge.detail["sides"], ["left"])
        self.assertEqual(edge.detail["clipped_by_frame"], ["left"])

    def test_interface_running_off_an_edge(self) -> None:
        rec = record(0)
        rec["border"]["right"].update({"crossings": 14, "action_band_density": 0.05})
        hits = detect_cut_off_content(context([rec]))
        self.assertEqual([(h.kind, h.detail["side"]) for h in hits], [("ui_off_edge", "right")])

    def test_panel_at_the_edge_and_text_cut_inside_it(self) -> None:
        panel = {"box": [1400, 200, 1916, 700], "rect": 0.98, "solid": 0.8, "color": "#ffffff", "background": False, "touches": ["right"]}
        inside = line((1500, 300, 1920, 330), clipped=("right",))
        hits = detect_cut_off_windows(context([record(0, texts=[inside], panels=[panel])]))
        self.assertEqual(kinds(hits), [("panel_at_edge_with_cut_text", "major")])
        hits = detect_cut_off_windows(context([record(0, texts=[line((1500, 300, 1800, 330))], panels=[panel])]))
        self.assertEqual(kinds(hits), [("panel_at_edge", "minor")])
        background = dict(panel, background=True)
        self.assertEqual(detect_cut_off_windows(context([record(0, panels=[background])])), [])


class Overlaps(unittest.TestCase):
    def test_text_on_text_and_duplicates(self) -> None:
        a, b = line((100, 100, 600, 140)), line((120, 110, 620, 150))
        hits = detect_overlaps(context([record(0, texts=[a, b])]))
        self.assertEqual(kinds(hits), [("text_on_text", "major")])
        same = line((100, 100, 600, 140))
        self.assertEqual(detect_overlaps(context([record(0, texts=[a, same])])), [], "near-identical boxes are one line")

    def test_a_chip_covering_page_text(self) -> None:
        page = line((247, 352, 1676, 378), bg="#ffffff")
        chip_text = line((1212, 314, 1642, 344), fg="#f6f6f8", bg="#25282f")
        chip = {"line": 1, "box": [1192, 295, 1662, 358], "color": "#25282f", "fill_share": 0.76}
        hits = detect_overlaps(context([record(0, texts=[page, chip_text], chips=[chip])]))
        self.assertEqual([h.kind for h in hits], ["chip_covers_text"])
        self.assertAlmostEqual(hits[0].detail["covered_share"], 6 / 26, places=3)
        self.assertEqual(hits[0].severity, "minor")


class SmallText(unittest.TestCase):
    def test_sizes_at_1080p_and_on_a_phone(self) -> None:
        texts = [line((100, 100, 400, 114), font=14.0), line((100, 200, 400, 220), font=20.0), line((100, 300, 400, 340), font=40.0),
                 line((100, 400, 900, 470), font=70.0)]
        hits = detect_small_text(context([record(0, texts=texts)]))
        found = {h.kind: h for h in hits}
        self.assertEqual(set(found), {"under_16_px", "under_24_px", "under_12_px_on_phone"})
        self.assertEqual(found["under_16_px"].severity, "major")
        phone = found["under_12_px_on_phone"]
        self.assertEqual((phone.detail["lines_failing"], phone.detail["lines"]), (3, 4))
        self.assertEqual(phone.severity, "note")

    def test_x_height_only_words_take_their_paragraph_neighbours_size(self) -> None:
        above = line((1014, 637, 1850, 659), font=23.0, cap=16.3, xh=11.9, stroke=2.6)
        below = line((1014, 672, 1122, 689), font=16.8, cap=11.9, xh=11.5, glyphs=8, stroke=2.6)
        fixed = lines_of(record(0, texts=[above, below]))
        self.assertEqual(fixed[1]["font"], 23.0)
        self.assertTrue(fixed[1]["font_from_neighbour"])
        alone = lines_of(record(0, texts=[below]))
        self.assertEqual(alone[0]["font"], 16.8)


class Contrast(unittest.TestCase):
    def test_minimums_for_normal_and_large_text(self) -> None:
        texts = [line((100, 100, 400, 120), font=20.0, contrast=3.5), line((100, 200, 400, 240), font=30.0, contrast=3.5),
                 line((100, 300, 400, 340), font=30.0, contrast=1.6), line((100, 400, 400, 420), font=20.0, contrast=4.6)]
        hits = detect_contrast(context([record(0, texts=texts)]))
        self.assertEqual(kinds(hits), [("below_2", "major"), ("below_minimum", "minor")])
        below = next(h for h in hits if h.kind == "below_minimum")
        self.assertEqual(below.detail["lines"], 1)


class Captions(unittest.TestCase):
    def test_text_under_and_beside_the_caption(self) -> None:
        cues = parse_vtt("WEBVTT\n\nc1\n00:00:00.000 --> 00:00:01.000 line:82%\nA caption line of some length\n")
        under = line((800, 900, 1100, 930))
        beside = line((48, 1029, 269, 1052))
        above = line((800, 500, 1100, 530))
        ctx = context(spatial_run(4, lambda i: [under, beside, above]), cues=cues)
        hits = detect_caption_collisions(ctx)
        self.assertEqual(kinds(hits), [("in_band_beside_caption", "minor"), ("under_caption_box", "major")])
        self.assertEqual(detect_caption_collisions(context(spatial_run(4, lambda i: [under]), cues=[])), [])


class Edges(unittest.TestCase):
    def test_busy_run_and_spill(self) -> None:
        busy = [record(i, edges=(0.09, 0.12, 0.16), spatial=False) for i in range(40)]
        self.assertEqual({h.kind for h in detect_layered_edges(context(busy))}, {"busy_frame"})
        short = [record(i, edges=(0.09, 0.12, 0.16) if i < 20 else (0.01, 0.01, 0.01), spatial=False) for i in range(40)]
        self.assertEqual(detect_layered_edges(context(short)), [], "under a second is not reported")
        panel = {"box": [100, 100, 700, 400], "rect": 0.98, "solid": 0.7, "color": "#ffffff", "background": False, "touches": []}
        spill = line((500, 200, 900, 230), bg="#ffffff")
        hits = detect_layered_edges(context([record(0, texts=[spill], panels=[panel])]))
        self.assertEqual(kinds(hits), [("spill", "major")])


def _frames_with(n, values):
    small = np.zeros((n, 45, 80), np.uint8)
    for t, v in enumerate(values):
        small[t] = v
    return small


class Transitions(unittest.TestCase):
    def test_flash_black_run_and_freeze(self) -> None:
        n = 160
        T = temporal(n)
        values = [120] * n
        values[30] = 250                      # one white frame
        for t in range(60, 80):               # 0.67 s of black
            values[t] = 0
        T["small"] = _frames_with(n, values)
        T["diff"] = np.array([0.0] + [abs(values[t] - values[t - 1]) for t in range(1, n)], float)
        T["luma_mean"] = np.array(values, float)
        T["luma_p99"] = np.array(values, float)
        recs = [record(i, spatial=False) for i in range(n)]
        hits = run_all(context(recs, T), only=["transitions", "freezes_and_motion"])
        by_kind = {}
        for h in hits:
            by_kind.setdefault(h.kind, []).append(h)
        self.assertEqual([h.frame for h in by_kind["flash_frame"]], [30])
        self.assertEqual({h.severity for h in by_kind["black_frames"]}, {"major"})
        self.assertNotIn("blank_frames", by_kind, "the flash is reported once, as a flash")
        frozen = by_kind["freeze"]
        self.assertGreaterEqual(frozen[0].detail["seconds"], 1.5)

    def test_a_crossfade_between_text_slides_is_a_double_exposure(self) -> None:
        n = 60
        T = temporal(n)
        a = np.full((45, 80), 230, np.uint8)
        a[10:14, 10:70] = 30
        b = np.full((45, 80), 230, np.uint8)
        b[11:15, 12:72] = 30
        frames = []
        for t in range(n):
            alpha = min(1.0, max(0.0, (t - 20) / 15))
            frames.append(np.round((1 - alpha) * a + alpha * b).astype(np.uint8))
        T["small"] = np.stack(frames)
        # The sliding blend fit as the sampler would compute it at thumbnail size.
        from frame_qa.sampler import _blend_fit

        fits = [(1.0, 0.0, 0.0)] * 4 + [_blend_fit([f.astype(np.float32) for f in frames[k - 4:k + 5]], 24) for k in range(4, n - 4)] + [(1.0, 0.0, 0.0)] * 4
        T["blend_error"] = np.array([f[0] for f in fits])
        T["blend_share"] = np.array([f[1] for f in fits])
        T["blend_distinct"] = np.array([f[2] for f in fits])
        T["diff"] = np.array([0.0] + [float(np.abs(frames[t].astype(float) - frames[t - 1]).mean()) for t in range(1, n)])
        text_a = [line((200, 240, 1700, 320))]
        recs = [record(i, texts=text_a if i < 30 else [line((240, 260, 1740, 340))]) for i in range(n)]
        ctx = context(recs, T)
        ctx.transitions = classify_transitions(ctx)
        self.assertEqual([e["type"] for e in ctx.transitions], ["dissolve"])
        hits = detect_transitions(ctx)
        self.assertEqual(kinds(hits), [("double_exposure", "major")])

    def test_text_moving_fast_and_a_camera_spike(self) -> None:
        n = 60
        T = temporal(n)
        T["shift_response"] = np.full(n, 0.9)
        T["aligned_gain"] = np.full(n, 0.9)
        T["shift_x"][30] = 40.0
        recs = []
        for i in range(n):
            if i % 2 == 0:
                speed = 12.0 if 10 <= i <= 30 else 0.1
                recs.append(record(i, texts=[line((100, 100, 600, 140))], motion={"boxes": 1, "median_px": speed, "max_px": speed}))
            else:
                recs.append(record(i, spatial=False))
        hits = detect_freezes_and_motion(context(recs, T))
        self.assertIn(("text_motion", "major"), kinds(hits))
        self.assertIn(("motion_spike", "minor"), kinds(hits))


if __name__ == "__main__":
    unittest.main()
