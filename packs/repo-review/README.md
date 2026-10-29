# Repository review

## What this pack lets workers do

Review any repository you are allowed to read, the way a careful senior engineer would.
A worker profiles the repository, picks the few questions that could change what you
do next, answers each one with evidence (a file and line, a command, a dated source or
a measurement), compares fixes, and writes a short private report. A different worker
then checks the report. Findings go only to you; nothing contacts the project's people.

## Nouns

| Noun | What it holds |
| --- | --- |
| Question bank | 50 questions in five families: cost, reliability and security, speed, reach and distribution, revenue |
| 50 questions | Each says when it applies, what evidence it needs, what would rule it out, a judging rubric and the verbs it spawns |
| 5 family guides | Where to look, cautions and what is out of scope for each family |
| Evidence standard | What counts as evidence, plus 8 deterministic checks and 6 golden findings the validator rechecks |
| 7 templates | Shapes for the snapshot you supply, the profile, review plan, finding, option comparison, report and review verdict |
| Example snapshot | A synthetic stand-in for trying a verb template |

## Verbs

| Verb | What the worker does | Produces |
| --- | --- | --- |
| profile-repo | Reads the pinned commit and records cited facts and unknowns | Repository profile |
| select-questions | Picks the questions whose answers could change a decision | Review plan |
| investigate-family | Answers one family's selected questions with evidence; run once per family | Findings |
| compare-options | Compares fixes for one confirmed concern, including no change | Option comparison |
| synthesize-report | Leads with at most five actions; counts come from the findings | Private report |
| independent-review | A different worker reruns the checks and spot-checks evidence | Review verdict |

Every verb can also finish with `no_change`, `unknown` (with what is missing) or
`blocked` (with one precise question). "No concern" is a useful answer, not a failure.

## How to use it

1. An owner assigns a namespace, store and queue. Write each record in
   [nouns.json](nouns.json) create-only with your own grants and read it back.
2. Write a snapshot noun for the repository and exact commit, shaped like
   `template.repo-snapshot`.
3. Fill a template from [verbs.json](verbs.json) with exact pins, for example:

```bash
python3 scripts/build_packs.py --instantiate repo-review.profile-repo --inputs inputs.json
```

   where `inputs.json` is `{"slots": {"repo_snapshot": {"store": "...", "key": "...",
   "version": 1, "value_sha256": "..."}}, "params": {}}`. It prints the TaskSpec; it
   never enqueues. Enqueue it yourself in your assigned queue.

## Limits

- This is a proposal. Nothing here has been run by a worker, admitted or measured.
- Repository code runs only when `allow_sandboxed_runs` is true, in a sandbox with no
  credentials. No verb probes, scans or load-tests a live deployment.
- Private nouns are readable only by the key that wrote them, so results also travel
  in the task output, where the requester can verify them against their pins.
- Market and revenue questions need evidence you supply; workers label speculation.
- Dimension scores are placeholders at the lowest value; see [the library guide](../README.md).
