# Evaluation design

## What this pack lets workers do

Run a fair, honest comparison of two or more ways of doing something. You fix the
arms, freeze the cases before anything runs, and a person commits the pass marks in
advance. Workers run every arm twice, score answers by exact match with plain code,
count cost per case from real usage, and report each mark as met, missed or unknown.
A missed mark stays missed. This generalizes Shamash's evaluation method.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The seven steps and the rules: opaque case ids, errors count as wrong, nulls stay null, unstable arms flagged |
| Exact-match scoring | A deterministic, zero-call scoring procedure |
| Worked example | Synthetic: 8 cases, two arms, two runs each and five pass marks, including an error counted as a miss, a missed mark and an unknown cost. The validator recomputes every number |
| Templates | Evaluation plan, arm, frozen-set manifest, pass marks, run record and evaluation report |

## Verbs

| Verb | Who | What happens | Produces |
| --- | --- | --- | --- |
| design-evaluation | agent | Question, arms, metrics and draft pass marks | Plan, arms, draft marks |
| freeze-set | agent | Hashes cases and labels; ids cannot leak labels | Frozen-set manifest |
| commit-pass-marks | person | Approves the marks before any run; they never change | Committed marks |
| run-arm | agent | Runs one arm over the whole set; twice per arm as separate attempts | Run record |
| score-run | agent | Exact-match scoring; reproduces the worked example first | Scored run |
| report-evaluation | agent | Every mark met, missed or unknown, with diagnoses | Report |
| review-evaluation | different agent | Recomputes the marks and checks the rules | Review |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only, write a question noun, then
fill `design-evaluation` from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate` and enqueue it yourself. The
[tool-discovery](../tool-discovery/README.md) trials reuse this method.

## Limits

- A proposal: the method has not been run through these verbs yet.
- Exact-match scoring suits labeled answers. A model judge may grade explanations
  only, with a person spot-checking its grades.
- `run-arm` spends only within the worker's own provider allowance; this pack grants none.
