# audio-and-narration-qa code

Standard-library deterministic checks for `packs/audio-and-narration-qa`:

- `audio_narration_qa.loudness`: ITU-R BS.1770-4 K-weighting biquad cascade at 48 kHz, gated integrated loudness (LUFS), short-term loudness range (LRA), sample peak (dBFS) and 4x oversampled inter-sample true peak (dBTP).
- `audio_narration_qa.dynamics`: sidechain pause-pumping detection across short inter-phrase pauses (`0.3 s` to `1.0 s`), hold-bridged ducking envelope generation (`1.2 s` hold), and second-difference edit-point click detection.
- `audio_narration_qa.pacing_and_asr`: WebVTT cue parser, speaking and articulation WPM pacing across cues and 10-second windows, caption-pause onset/offset sync checks, and normalized Levenshtein Character Error Rate (CER) gating against ASR transcripts.

Run `make check` to compile with `-W error` and run every unit test plus the worked-example recomputation.
