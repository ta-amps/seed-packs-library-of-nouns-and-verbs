# Continuous tuning

## What this pack lets workers do

A collection of nouns and verbs for tuning a small open model at one narrow task, round after round,
and keeping a change only when a rule committed before any scoring says so. Workers generate owned
made-up examples, curate them against contamination, freeze a test set and register its hashes,
train a QLoRA or LoRA adapter on free or local GPUs, score it by strict exact match, check that it
reloads to the same replies, and decide by the rule with a paired bootstrap. Keeping the champion is
a valid outcome, and a promotion moves only a private pointer. It builds on the
[evaluation design pack](../evaluation-design/README.md)'s exact-match scoring.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Rule and test registered before scoring; no contamination; owned data only; a private pointer, keeping is valid; the base license and the compute's terms |
| Procedures | Strict exact-match scoring, the paired bootstrap with portable draws, the three-fingerprint contamination check, reload equivalence |
| Promotion rule | The real pre-registered rule, version 1, with its source commit and digest `bf0fa821...` |
| Tool cards | The pack's tested code in [code/](code/README.md), and the full loop in Tessera pinned by commit and file digests |
| Templates | Promotion rule, learner spec, example batch, frozen test receipt, adapter card, run record, reload check, promotion decision, champion pointer, roll back record |
| Measured results | Published results on one made-up task each, with their limits |
| Decision checks | Nine checks on a decision, with two good and nine bad decisions the validator recomputes |
| Checklist, sources, test cases | What a person checks; 6 dated public sources; 8 made-up cases |
| Worked example | Made-up: 40 frozen rows with a real receipt, and two rounds under the real rule |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `register-rule` | person | Commit the promotion rule before any scoring |
| `generate-examples` | agent, no model | Owned rows from templates; labels computed |
| `curate-dataset` | agent, no model | Reject any row that shares a fingerprint with a held-out row |
| `freeze-test-set` | agent, no model | Register a test set's hashes before any scoring |
| `train-adapter` | agent, no model | QLoRA or LoRA on the worker's own or a free GPU |
| `evaluate` | agent, no model | Dev selects; the frozen test, fresh holdout and sanity set decide |
| `check-reload` | agent, no model | The saved adapter reloads to the same replies |
| `decide-promotion` | a different agent, no model | Apply the rule; anyone can recompute it |
| `promote-or-roll-back` | agent or person | Move the private pointer, or a person rolls it back |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose follow-up verbs.

## Measured results

On a frozen 150-row made-up test of typed tool calls, Meta's open-weight 1B model rose from 12.0% to
50.7% exact match over four rounds, and Meta's open-weight 3B model from 52.0% to 72.7% in one; a later 3B
round scored 79.3% but broke a schema guard and was kept out. Glimmer 30B rose from 93.3% to 99.3%
on a fresh holdout registered before scoring. Each is one made-up task with one seed.

## How to use it

Run `make check` in [code/](code/README.md) to recompute the worked example. Write the nouns in
[nouns.json](nouns.json) create-only with a key scoped to your team's surface, then fill a template
from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs
  through Tessera. The measured results came from the loop's own code, not from these templates.
- The worked example is made-up; its rows, receipt digests and decisions are real computations on
  made-up data, and no model was trained or scored for it.
- The pack's code recomputes decisions; training and scoring need the loop's GPU worker environment.
- A gain on one made-up task says nothing about other tasks or real traffic.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
