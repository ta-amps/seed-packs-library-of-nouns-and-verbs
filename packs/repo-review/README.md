# Repository review

## What this pack lets workers do

A collection of nouns and verbs for reviewing a code repository with evidence. A worker
profiles the repository, picks the few questions that could change what you do next,
answers each with evidence (a file and line, a command, a dated source or a
measurement), compares fixes and writes a short report. A different worker then checks
it. Findings stay in your team's scope, and nothing contacts the project's people.

## Nouns

| Noun | What it holds |
| --- | --- |
| Question bank | 50 questions in five families: cost, reliability and security, speed, reach and distribution, revenue |
| 50 questions | Each says when it applies, what evidence it needs, what would rule it out, a judging rubric and the verbs it spawns |
| 5 family guides | Where to look, cautions and what is out of scope for each family |
| Evidence standard | What counts as evidence, plus 8 deterministic checks and 9 golden findings the validator rechecks |
| 7 templates | The snapshot you supply, the profile, review plan, finding, option comparison, report and review verdict |
| Example snapshot | A synthetic stand-in for trying a verb template |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| profile-repo | Reads the pinned commit and records cited facts and unknowns | Repository profile |
| select-questions | Picks the questions that could change a decision and proposes one investigate-family verb per family | Review plan |
| investigate-family | Answers one family's selected questions with evidence | Findings |
| compare-options | Compares fixes for one confirmed concern, including no change | Option comparison |
| synthesize-report | Leads with at most five actions; counts come from the findings | Report |
| independent-review | A different worker reruns the checks and spot-checks evidence | Review verdict |

Every verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs and nouns. "No concern" is a useful answer. Some questions point to the
security, cost and docs packs for deeper follow-up.

## How to use it

Write a snapshot noun for the repository and exact commit, shaped like
`template.repo-snapshot`. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: no worker has run these verbs, and nothing is admitted or measured.
- Repository code runs only when `allow_sandboxed_runs` is true, in a sandbox with no
  credentials. No verb probes, scans or load-tests a live deployment.
- Market and revenue questions need evidence you supply; workers label speculation.
- Built-in quality scores start at the lowest value until measured; see the [library guide](../README.md).
