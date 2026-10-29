# Evaluation design

## What this pack lets workers do

A collection of nouns and verbs for fair, pre-registered evaluations of two or more
ways of doing something. You fix the arms, freeze the cases before anything runs, and a
person commits the pass marks in advance. Workers run every arm twice, score answers by
exact match with plain code, count cost per case from real usage, and report each mark
as met, missed or unknown. A missed mark stays missed.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The seven steps and the rules: opaque case ids, errors count as wrong, nulls stay null, unstable arms flagged |
| Exact-match scoring | A deterministic, zero-call scoring procedure |
| Worked example | Synthetic: 8 cases, two arms, two runs each and five pass marks, including an error counted as a miss, a missed mark and an unknown cost |
| Templates | Evaluation plan, arm, frozen-set manifest, pass marks, run record and evaluation report |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| design-evaluation | agent | Question, arms, metrics and draft pass marks |
| freeze-set | agent | Hashes cases and labels; ids cannot leak labels |
| commit-pass-marks | person | Approves the marks before any run; they never change |
| run-arm | agent | Runs one arm over the whole set; twice per arm as separate attempts |
| score-run | agent | Exact-match scoring; reproduces the worked example first |
| report-evaluation | agent | Every mark met, missed or unknown, with diagnoses |
| review-evaluation | different agent | Recomputes the marks and checks the rules |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs, such as the run-arm attempts a plan needs.

## How to use it

Write a question noun. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface. The tool discovery, benchmark and cost packs
reuse this method.

## Limits

- A proposal: the method has not been run through these verbs yet.
- Exact-match scoring suits labeled answers; a model judge may grade explanations only,
  with a person spot-checking its grades.
- `run-arm` spends only within the worker's own provider allowance; this pack grants none.
