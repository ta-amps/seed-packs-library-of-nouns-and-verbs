# Audio and narration QA

## What this pack lets workers do

A collection of nouns and verbs for deterministic audio, mix and narration quality checks on
narrated videos and podcasts. In plain language, nouns are **task objects** (loudness and pacing
specs, ducking rules, pinned standard-library code, schemas and made-up worked examples) and
verbs are **tasks** a worker claims. Workers measure ITU-R BS.1770-4 integrated loudness, loudness
range and 4x oversampled true peak, detect sidechain pause-pumping and edit-point splice clicks,
verify speaking WPM pacing and WebVTT caption-pause alignment, and gate synthesized or recorded
speech against its script via normalized ASR Character Error Rate (CER).

## Nouns

| Noun (task object) | What it holds |
| --- | --- |
| Guardrails | Bind measurements to exact audio SHA-256; bridge short pauses instead of fast sidechain release; never treat automated metrics as creative mix sign-off |
| `spec.audio-narration-gates` | BS.1770 loudness (`-16 LUFS +/- 1 LU`, `-1.0 dBTP` true peak), pause-pumping (`>= 3 dB` rise in `0.3..1.0 s` pauses), edit click (`12x` 2nd-difference impulse), WPM (`140..165` target, `110..180` bounds), caption sync (`0.25 s` start, `0.50 s` end) and ASR CER (`<= 0.02` pass, `> 0.05` fail) |
| `rules.hold-ducking-envelope` | Deterministic `1.2 s` phrase-bridging music ducking envelope rule that prevents sidechain pumping |
| `tool.audio-narration-qa` | Tested standard-library Python package in [code/](code/README.md), pinned by path, file count and digest |
| `template.narration-qa-report` | JSON Schema for a digest-pinned audio and narration QA report |
| Worked example | Made-up narrated cut (`example.narration-cut`) and recomputed QA report (`example.qa-report`) |

## Verbs

| Verb (task) | Who | What happens |
| --- | --- | --- |
| `measure-loudness-and-peaks` | agent, no model | Measure BS.1770-4 integrated LUFS, short-term LRA, sample peak and 4x true peak on PCM audio |
| `audit-ducking-and-clicks` | agent, no model | Detect sidechain pause-pumping, emit a `1.2 s` hold-bridged duck envelope, and flag edit-point clicks |
| `check-pacing-and-caption-sync` | agent, no model | Check speaking and articulation WPM, 10 s pacing windows, and WebVTT caption onset/offset alignment |
| `gate-narration-asr-cer` | agent, no model | Compute normalized Levenshtein CER between reference script and ASR transcript and gate mispronunciations or dropouts |
| `compile-narration-qa-report` | agent, no model | Combine loudness, dynamics, pacing, caption sync and ASR CER into one digest-pinned QA report |

## How to use it

Run `make check` in [code/](code/README.md) to compile with warnings treated as errors and execute
all unit tests plus the worked-example recomputation from `source.json`.

## Limits

- Quarantined, unverified proposal until reviewed: this pack is not installed, imported, admitted or
  activated, and no worker has claimed or run these tasks through Tessera.
- The worked example in `source.json` is made-up.
- CER gating catches dropped clauses, hallucinated TTS words and severe phonetic errors, but does
  not judge vocal warmth, prosody naturalness or musical phrasing; a person still listens.
