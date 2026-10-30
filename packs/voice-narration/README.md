# Voice narration

## What this pack lets workers do

A collection of nouns and verbs for narration with a text-to-speech voice, labeled as AI. Workers
prepare a pronunciation lexicon for the words a voice model may misread, synthesize every line with
a licensed model's stock voice on their own machine, log the exact text the model received, measure
every take's loudness, peaks, noise floor, silences and pace with a round-trip transcript check,
choose takes by a rule fixed before scoring, and place the chosen lines on the beats of a cut plan.
A person listens to every line and confirms each lexicon word by ear. The
[narrated explainer video pack](../narrated-explainer-video/README.md) times its captions from these
placements; a person's own recorded voice uses the
[video showcase pack](../video-showcase/README.md)'s `record-narration` instead.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Label every AI voice; never clone or imitate a real person's voice; a license that permits the use, checked first; the script's words never change |
| Lexicon rules | Phonemes, respellings and the engine's input form; auditions; whole-word application; a person's ear decides |
| Take selection rule | Drop invalid, truncated and clipped takes; lowest error rate; pace nearest the target; keep every take |
| Audio measurements | Loudness, true peak, full-scale samples, noise floor, silences, pauses, pace, the edge trim and default limits |
| Fitting lines to beats | Starts inside beats, gaps, headroom, trims at measured pauses, track length |
| Voice model card | An open 82-million-parameter model with phoneme input: license, revision and weight digests, checked against its publisher |
| Templates | Voice model card, narration script, lexicon, synthesis log, line measurements, take choice, narration track, listening record |
| Narration checks | Seven checks on a narration, with one good and seven bad candidates the validator recomputes |
| Checklist, sources, test cases | A person's listening checklist; 8 dated public sources; 8 synthetic cases |
| Worked example | Synthetic: two lines with a coined street name and an acronym, five takes, the rule's choice and the placed 20-second track |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `prepare-lexicon` | agent | Phonemes and respellings for words the model may misread, with auditions |
| `synthesize-lines` | agent, no model | Seeded takes on the worker's machine, the lexicon applied, every take logged |
| `measure-lines` | agent, no model | Loudness, peaks, silences, pace and a round-trip transcript for every take |
| `select-takes` | agent, no model | One take per line by the rule fixed in advance |
| `place-on-beats` | agent, no model | One narration track per cut, every line on its beat |
| `listen-and-approve` | person | Listen to everything, confirm the lexicon by ear, approve or hold |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up verbs.
Verbs for a person are claimed by people, never by an agent.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface,
then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs
  through Tessera. They generalize the narration work for ta-amps's own explainer video on October 29
  and 30, 2026, which was still in production when this pack was written.
- The worked example is synthetic and has no audio; its measurements are plausible values, and the
  library's tests recompute only its arithmetic: pace, take choice, loudness spread and placements.
- A recognizer's transcript is a proxy for intelligibility. It cannot hear stress, warmth or
  artifacts, so a person listens before anything is used.
- The loudness and pace limits are defaults from one production, not standards.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
