# Video QA checks

Deterministic checks the video QA pack's verbs run inside a claimed verb, on the logs FFmpeg writes and
on the bytes of an MP4, never on decoded media. Python 3.10 or later, standard library only.

- `captions`: parse WebVTT and SRT, lint every cue, compare sidecars, time cues against speech.
- `ffmpeg_logs`: read blackdetect, freezedetect, silencedetect, ebur128, astats and metadata print output.
- `checks`: blank, frozen, cadence, loudness, silence and clipping rows against a declared plan.
- `mp4`: read boxes for fast start, fragments, edit lists, codecs, profile, colour, rate and audio.
- `layout`: a legibility proxy, WCAG contrast with unrounded thresholds, reading time and safe areas.
- `rows` and `report`: one way to build rows, and one report per file with a verdict.

```bash
make check                                    # compile, then every test
python -m video_qa_checks captions --vtt CUT.vtt --srt CUT.srt --speech SPEECH.json
python -m video_qa_checks filespec --mp4 CUT.mp4 --spec SPEC.json
```

The tests recompute the pack's worked example from [source.json](../source.json), check the caption
limits against the video showcase style guide, the keep-out boxes against the video and motion
pack's aspect rules and the contrast ratios against the accessibility audit pack's recorded example, and read MP4s built byte by byte in the tests. Log fixtures are text FFmpeg 7.0.2
wrote while analysing made-up test sources. Nothing here runs FFmpeg, calls a model, opens a network
connection or writes inside the seed-pack library. MIT license, written for this pack by ta-amps.
