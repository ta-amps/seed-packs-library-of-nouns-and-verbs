# Video editing

## What this pack lets workers do

A collection of nouns and verbs for editing a video from its script, with every revision kept and a
person locking the cut. Workers lay the cut out as an edit decision list: shots paced against the
words spoken over them, J and L cuts that let the voice carry across picture changes, b-roll on the
words it illustrates, and transitions chosen on purpose. They measure pacing per shot, plan the mix
with ducking and loudness targets, check colour and contrast on the render, plan reframes for other
aspect ratios, conform the list and write the export spec. Each review finding is answered in a new
version with a revision note; a person watches and locks the cut. Nothing here releases a video.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Keep every version; fix the cause, not the frame; the picture supports the words; length from beats, not padding |
| Pacing rules | Words per second, reading need, beat gaps and five verdicts: rushed, slack, unreadable, dense, long |
| J and L cut, b-roll and transition rules | Split edits in measured pauses, inserts on their words, hard cuts by default and no dissolve over text |
| Colour and audio mix rules | One palette, unrounded contrast, luma jumps; the voice first, ducking, one bed, loudness targets |
| Reframing, conform and export rules | Per-shot crops with text at full size; resolved events, totals and delivery profiles with budgets |
| Templates | Edit list, pacing report, mix plan, colour report, reframe plan, export spec, conform record, revision note, lock record |
| Edit checks | Seven checks on an edit summary, with one good and seven bad summaries the validator recomputes |
| Checklist, sources, test cases | What a person checks before locking; 5 dated public sources; 7 made-up cases |
| Worked examples | Made-up: a 30-second edit list, its pacing report, a mix plan, two export profiles and a revision note |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `draft-edit-list` | agent | Shots, split edits, b-roll, transitions, beats and a reason for every event |
| `check-pacing` | agent, no model | Every shot's rate, reading need and beat gaps against the pacing rules |
| `plan-mix` | agent | Stems, licences, ducking, one bed with its seed, effects on events, targets |
| `check-color` | agent, no model | Per-shot luma and chroma on the render, jumps and unrounded contrast |
| `plan-reframes` | agent | A crop window per shot for each other aspect, labels kept |
| `write-export-spec` | agent | Delivery profiles with codec, colour, audio, fast start and budgets |
| `conform-edit` | agent, no model | Every event resolved, no gap or overlap, totals equal the plan |
| `revise-edit` | agent | A new version answering findings at their causes, with a revision note |
| `lock-cut` | person | Watch the whole cut with sound, then lock it or send it back |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Rendering uses the [video and motion pack](../video-motion/README.md), and the
[video review pack](../video-review/README.md) supplies the findings that `revise-edit` answers.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs
  through Tessera.
- The worked examples are made-up; the library's tests recompute only the pacing arithmetic.
- Pacing limits, duck depths and loudness targets are defaults from one production, not standards.
- The pack plans and checks an edit; it ships no editor or renderer, and a pacing verdict cannot tell
  a deliberate pause from a slack one. A person decides.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
