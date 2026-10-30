# Annoyance hunt

## What this pack lets workers do

A collection of nouns and verbs for hunting the friction and papercuts people meet, from their point
of view: confusing copy, extra clicks, slow steps, surprising defaults, noisy output, repeated
prompts, dead ends, inconsistent naming and things that work but feel wrong. Workers walk friction
tours as time-boxed charters for websites, command lines, videos and docs, counting actions against
the shortest path, waits, repeated questions and lines printed, and quote every hesitation. They read
permitted feedback for complaints in people's own words, count how often each annoyance happens and
how much it hurts, and rank by frequency times pain. A person confirms the ranking, and each
annoyance becomes a finding with who it affects, how to reproduce it, a fix and a guard.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules, from the user's point of view |
| Guardrails | In their words; describe the product, never blame the person; no personal data |
| Friction catalog | Nine categories with signals, a measure, an example per medium and the heuristic each relates to |
| Pain scale and frequency rule | Pain 1 to 4, frequency levels from counted shares, score, rank, ties and severity |
| Friction tours | Eighteen tours: five for websites, five for command lines, four for videos and four for docs |
| Annoyance checks | 16 checks on a finding, with 3 good and 16 bad findings the validator recomputes |
| Templates | Friction session, complaint extract, annoyance log and a person's ranking confirmation |
| Sources, checklist and test cases | 3 dated public sources; what a person checks; 6 synthetic cases |
| Worked examples | Four charters, a session, a complaint extract, a ranked log, a confirmation and a finding |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `draft-friction-charters` | agent | Charters from the tours, in the exploratory testing form |
| `hunt-annoyances` | agent or person | One charter walked and counted, every hesitation quoted at its step |
| `collect-complaints` | agent | Complaints from permitted feedback, counted, with nothing personal kept |
| `rank-annoyances` | agent, no model | Duplicates folded, frequency and pain counted, ranked by the rule |
| `confirm-ranking` | person | Pain and groups confirmed or changed with reasons, taste calls marked |
| `record-annoyance-findings` | agent | A finding per confirmed annoyance, and a palette brief for each taste call |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Charters and debriefs follow [exploratory testing charters](../exploratory-testing-charters/README.md);
each category points at its heuristic in [usability heuristics review](../usability-heuristics-review/README.md);
fixes go through [findings to fixes](../findings-to-fixes/README.md), where a different worker reruns
the same reproduction and measure, and taste calls through [taste palettes](../taste-palettes/README.md).
A disputed pain rating can go to the [persona panel and second opinion](../persona-panel-second-opinion/README.md) pack first.

## Worked examples

All synthetic: a volunteer site, its roster command line, its 45-second explainer and its docs.
Twelve sessions and forty permitted messages give ten annoyances. Signing up takes seven actions
where three would do, in four of five sessions, at pain 3, so it scores 12, ranks first and is P2; a
video that never shows where to sign up also scores 12 but rests on two viewers, so it is flagged low
confidence and stays P3. The coordinator lead lowers that one's pain with a reason and marks a faint
confirmation note as a matter of taste: it is still a finding, and its fix goes to a palette.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The examples are synthetic; the library's tests recompute their levels, scores and ranks only.
- An agent walking a persona's path is not the person; its quotes are a tester's words, and real
  sessions with people need consent and the moderated testing this library does not yet hold.
- Frequency is only as good as its opportunities; small counts are flagged, not hidden.
- The checks catch missing and inconsistent fields, not a wrong pain rating; a person confirms it.
