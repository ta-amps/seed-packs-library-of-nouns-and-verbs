# Video audience acceptance

## What this pack lets workers do

A collection of nouns and verbs for testing whether a video's intended viewers understand it, with
pass criteria fixed before any session. Workers plan the test: audience segments, video-specific
tasks such as saying in one sentence what it does after one viewing, naming who it is for and the
next step, recalling a number, pointing at a confusing or boring moment, reading the AI-voice label,
or getting the gist with the sound off. A person recruits viewers and runs each consented session.
Two scorers mark answers against fixed keys, the fixed criteria decide, and every miss becomes a
timestamped finding about the cut. Results describe the people asked, never viewers in general.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Consent first and notes only; criteria fixed before sessions; the video is tested, not the viewer; no generalizing |
| Method | One viewing on the viewer's own device, open questions first, no hints, moments found by scrubbing |
| Task bank | Eight video-specific tasks with their keys and how each is scored |
| Templates | Acceptance plan, session notes, scored answers, acceptance decision |
| Acceptance checks | Five checks on a decision, with one good and five bad decisions the validator recomputes |
| Test cases | 5 synthetic cases, from a criterion lowered after sessions to a summary that generalizes |
| Worked examples | Synthetic: a plan for ten viewers in two segments, scored answers and the decision they give |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `plan-acceptance` | agent | Segments, tasks, consent line and pass criteria, dated before any session |
| `run-session` | person | Consent, one viewing, the tasks in order, answers noted in the viewer's words |
| `score-answers` | a different agent | Answers marked against keys by two scorers, with their agreement |
| `decide-acceptance` | agent, no model | The fixed criteria applied: counts, shares, met, missed or unknown |
| `write-uat-findings` | agent | Each miss and each named moment proposed as a finding with its fix verb |

Criteria agreement and the final go or no-go are the
[user acceptance testing pack](../user-acceptance-testing/README.md)'s `agree-criteria` and `sign-off`,
both a person's verbs; this pack adds only what a video needs. Findings route through the
[video review pack](../video-review/README.md)'s fix routes, and the fixed cut is re-reviewed there. Each verb can also end with `no_change`, `unknown` or `blocked`, and
proposes follow-up verbs instead of enqueueing them.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and nobody has been asked anything
  with these verbs.
- A few viewers per segment find comprehension problems; they do not measure an audience, and the
  pack reports counts, never audience percentages.
- Keys and pass marks are the planner's choices, fixed in advance, not standards.
- General acceptance testing of a site or app, usability and accessibility are other packs' work. The worked examples are
  synthetic; the library's tests recompute the decision from the plan and the scores.
