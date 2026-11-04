# Measured claims

## What this pack lets workers do

A collection of nouns and verbs for technical notes, summaries and commit messages whose every
claim says how it is known. The costly failure in agent work is a confident sentence that nobody
ran: a commit message stating a result the code does not produce, a number copied from another
note into a conclusion, a counter that was never measured written as zero, or a wrong claim
quietly edited away so nobody learns how it happened. Workers label each claim as measured here,
read, verified, reported, designed or unverified with the evidence that label needs, rest
conclusions only on measured, read or verified claims, reproduce reported numbers before relying
on them, append corrections and state what the note does not establish.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules: evidence as part of every measured claim; summaries and commit messages are claims too |
| Claim labels | Six labels and the evidence each needs; a claim without a label is unverified |
| Reproduction rules | Tolerance first, n stated, not reproduced means a correction, could not run means unknown |
| Comparison rules | Sample sizes that can separate options, isolated shared state, a frozen runner, honest exit statuses |
| Claim checks | 12 deterministic checks with 2 made-up good and 12 made-up bad notes, rechecked by `make check` |
| Templates | Note, reproduction, correction and note audit |
| Worked examples | A reported number that did not reproduce, and the correction appended for it |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| label-claims | agent | Sorts every claim by how it is known and ties conclusions to their evidence |
| reproduce-claim | agent, deterministic | Reruns a claimed number with the tolerance fixed first |
| record-correction | agent | Appends what was claimed, what was true and how the error was made |
| audit-note | a different agent or a person | Checks labels, evidence, conclusions, zeros, corrections and limits |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Errors become findings in [findings to fixes](../findings-to-fixes/README.md);
a comparison between options that needs to be fair goes to [evaluation design](../evaluation-design/README.md).

## Worked examples

All made-up. The good note sorts six claims across all six labels, rests its two conclusions on
measured and read claims, lists one unmeasured value with its reason and keeps a correction: a
reported 180 tokens per step measured 820, 820 and 821 against a 5 percent tolerance set first.
Each bad note breaks one rule, such as a conclusion resting on that unreproduced number.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Label claims before a note, summary or commit message is relied on.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The claim checks catch missing evidence and unsupported conclusions, not a wrong measurement; audits and reproductions still matter.
- The sample-size rule is a standard two-proportion calculation, a starting point rather than a substitute for a planned evaluation.
