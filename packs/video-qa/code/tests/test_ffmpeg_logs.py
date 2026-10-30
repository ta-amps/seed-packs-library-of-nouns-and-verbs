"""The parsers on log text FFmpeg 7.0.2 wrote while analysing synthetic test sources (testsrc2, sine, silence)."""

from __future__ import annotations

import unittest

from video_qa_checks.ffmpeg_logs import (close_open, parse_astats_overall, parse_blackdetect, parse_ebur128_frames,
                                         parse_ebur128_summary, parse_freezedetect, parse_metadata_print,
                                         parse_silencedetect)

PICTURE = """[blackdetect @ 0x7110640038c0] black_start:2 black_end:3 black_duration:1
[freezedetect @ 0x711064003d40] lavfi.freezedetect.freeze_start: 2
[freezedetect @ 0x711064003d40] lavfi.freezedetect.freeze_duration: 1
[freezedetect @ 0x711064003d40] lavfi.freezedetect.freeze_end: 3
[freezedetect @ 0x711064003d40] lavfi.freezedetect.freeze_start: 3.3
[freezedetect @ 0x711064003d40] lavfi.freezedetect.freeze_duration: 1.7
[freezedetect @ 0x711064003d40] lavfi.freezedetect.freeze_end: 5
"""
SILENCE = """[silencedetect @ 0x747490003380] silence_start: 1.999833
[silencedetect @ 0x747490003380] silence_end: 3.500021 | silence_duration: 1.500188
[silencedetect @ 0x747490003380] silence_start: 5.25
"""
CLIPPED = """[Parsed_astats_0 @ 0x7c548c003340] Overall
[Parsed_astats_0 @ 0x7c548c003340] Peak level dB: 0.000265
[Parsed_astats_0 @ 0x7c548c003340] RMS level dB: -5.829687
[Parsed_astats_0 @ 0x7c548c003340] Flat factor: 31.148508
[Parsed_astats_0 @ 0x7c548c003340] Peak count: 31760.000000
[Parsed_astats_0 @ 0x7c548c003340] Number of samples: 144000
"""
EBUR = """[Parsed_ebur128_0 @ 0x7ba6f0003240] t: 0.0999792  TARGET:-23 LUFS    M:-120.7 S:-120.7     I: -70.0 LUFS       LRA:   0.0 LU  FTPK: -38.1 dBFS  TPK: -38.1 dBFS
[Parsed_ebur128_0 @ 0x7ba6f0003240] t: 3.999979   TARGET:-23 LUFS    M:  -9.8 S: -17.5     I: -11.3 LUFS       LRA:   7.0 LU  FTPK:  -6.1 dBFS  TPK:  -6.1 dBFS
[Parsed_ebur128_0 @ 0x7ba6f0003240] Summary:

  Integrated loudness:
    I:         -10.9 LUFS
    Threshold: -26.3 LUFS

  Loudness range:
    LRA:         5.2 LU
    Threshold: -36.3 LUFS
    LRA low:   -19.8 LUFS
    LRA high:  -14.5 LUFS

  True peak:
    Peak:       -6.1 dBFS
"""
SCENES = """frame:0    pts:0       pts_time:0
lavfi.scene_score=0.000000
frame:1    pts:33      pts_time:0.033
lavfi.scene_score=0.022045
frame:2    pts:67      pts_time:0.067
lavfi.scene_score=0.004663
"""


class Parsers(unittest.TestCase):
    def test_blackdetect(self) -> None:
        self.assertEqual(parse_blackdetect(PICTURE), [{"start_s": 2.0, "end_s": 3.0, "duration_s": 1.0}])

    def test_freezedetect_pairs_start_and_end(self) -> None:
        self.assertEqual(parse_freezedetect(PICTURE), [{"start_s": 2.0, "end_s": 3.0, "duration_s": 1.0},
                                                       {"start_s": 3.3, "end_s": 5.0, "duration_s": 1.7}])

    def test_silence_still_open_at_the_end(self) -> None:
        silences = parse_silencedetect(SILENCE)
        self.assertEqual(silences[0], {"start_s": 1.999833, "end_s": 3.500021, "duration_s": 1.500188})
        self.assertEqual(silences[1], {"start_s": 5.25, "end_s": None, "duration_s": None})
        self.assertEqual(close_open(silences, 6.0)[1], {"start_s": 5.25, "end_s": 6.0, "duration_s": 0.75})

    def test_astats_overall(self) -> None:
        self.assertEqual(parse_astats_overall(CLIPPED), {"peak_level_db": 0.000265, "rms_level_db": -5.829687,
                                                          "flat_factor": 31.148508, "peak_count": 31760.0,
                                                          "samples": 144000.0})
        self.assertEqual(parse_astats_overall("nothing here")["peak_level_db"], None)

    def test_ebur128_summary_and_frames(self) -> None:
        self.assertEqual(parse_ebur128_summary(EBUR), {"integrated_lufs": -10.9, "lra_lu": 5.2, "true_peak_dbtp": -6.1})
        frames = parse_ebur128_frames(EBUR)
        self.assertEqual(frames, [{"t_s": 0.0999792, "momentary_lufs": -120.7, "short_term_lufs": -120.7},
                                  {"t_s": 3.999979, "momentary_lufs": -9.8, "short_term_lufs": -17.5}])
        self.assertEqual(parse_ebur128_summary("no summary"), {"integrated_lufs": None, "lra_lu": None,
                                                               "true_peak_dbtp": None})

    def test_metadata_print(self) -> None:
        self.assertEqual(parse_metadata_print(SCENES, "lavfi.scene_score"),
                         [(0.0, 0.0), (0.033, 0.022045), (0.067, 0.004663)])
        self.assertEqual(parse_metadata_print(SCENES, "lavfi.signalstats.YMIN"), [])


if __name__ == "__main__":
    unittest.main()
