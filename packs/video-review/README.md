# Video review

## What this pack lets workers do

A collection of nouns and verbs for reviewing a video with a fixed rubric, run by a person or a worker
that did not make it. Workers make panels of the exact bytes: a one-per-second contact sheet, hook,
ending and transition strips, and the same frames at the sizes people watch on. They trace every
number to its evidence, then answer a ten-area rubric and write each problem as a timestamped finding
with a severity, what was seen, how it was seen and the verb that would fix its cause. A second
reviewer's answers are compared where they disagree, a person watches and listens, findings are
routed to fix verbs, and the fixed cut is re-reviewed against the same finding ids. A review
recommends; only a person approves publishing.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | The reviewer did not make the cut; evidence for every finding; every number traced; a review binds to bytes; only a person approves release |
| Rubric | Ten areas, from story and hook to labels and technical, with 30 questions, how each is answered, its pass mark and the severity of a failure |
| Severity guide | Blocker, major, minor and note, their responses, and how they map to findings to fixes |
| Method | Panels first, display-scale sheets, claims before story, measure what matters, a second reviewer, a person listening |
| Fix routes | The verb that fixes each cause, from the edit to the script, the stage, a capture or the render |
| Templates | Review scope, panel set, claim trace, review findings, review comparison, listening record, fix routing, re-review |
| Review checks | Seven checks on a review, with one good and seven bad reviews the validator recomputes |
| Checklist, sources, test cases | What a person does when watching; 6 dated public sources; 7 made-up cases |
| Worked examples | Made-up: a scope, a claim trace with a disputed number, seven findings and the re-review of the fixed cut |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `make-panels` | agent, no model | Contact sheet, strips and display-scale sheets of one hashed file |
| `trace-claims` | a different agent | Every number and claim traced to a record or dated source |
| `review-cut` | person or different agent | The rubric, timestamped findings, scores, top fixes and a decision |
| `compare-reviews` | a different agent | Agreements, disagreements, a second look and who was right |
| `watch-and-listen` | person | The whole cut with sound on headphones and a phone, and muted once |
| `route-findings` | agent | Findings grouped by cause, each group's fix verb, records proposed |
| `re-review` | person or different agent | Every earlier finding fixed, not fixed, regressed or gone, on the new bytes |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Measurements come from the [video QA pack](../video-qa/README.md); findings stay
on the record through [findings to fixes](../findings-to-fixes/README.md). The rubric judges the
video itself: the page and player around it belong to the
[accessibility audit pack](../accessibility-audit/README.md)'s `check-media`, a single frame with
known layout to the [screenshot design review pack](../screenshot-design-review/README.md), and real
viewers to the [video audience acceptance pack](../video-uat/README.md).

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these Tasks
  through the shared work queue. Its rubric was applied by hand to ta-amps's own 3:00 film while this pack was
  written; that review is kept privately and is not a run of these verbs.
- The worked examples are made-up; the library's tests recheck their counts and consistency only.
- An agent cannot listen, and one reviewer is one opinion; the person's verb and the comparison exist
  for that reason. A rubric judges the cut, not an audience.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
