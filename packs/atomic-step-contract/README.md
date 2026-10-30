# Atomic step contract

## What this pack lets workers do

A collection of nouns and verbs for giving each atomic step exactly what it needs, the way a
colleague hands over a task with the file attached instead of forwarding the whole thread. Long
work done as many small steps fails in predictable ways: a step is handed a growing transcript,
a "read-only" step still holds a shell, a refusal says "no" without saying what is allowed so the
step guesses the same thing again, and a per-step overhead nobody measured makes fine slicing
look expensive. Workers define step kinds, audit that grants deny on the wire, assemble bounded
packets, check every returned patch, review refusals and measure the overhead before slicing finer.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and the rules: one step, one job; attempt whole, split on a failed check; observe after a failure |
| Packet rules | What a step always receives, may fetch through the runner, and never sees; push versus pull |
| Grant rules | Grants that deny by construction; no shell in a read-only step; no question at run time; verdicts for audits |
| Refusal rules | Every refusal names the legal set; repeats get a reminder; the binding limit is named |
| Patch rules | State returned as named fields, admitted or rejected by the runtime contract only |
| Overhead model | The break-even hit rate for slicing a step into k: (k - 1)P / (kP + C), and how to measure P on the wire |
| Step checks | 11 deterministic checks with 2 synthetic good and 11 synthetic bad packets, rechecked by `make check` |
| Templates | Step kind, step packet, grant audit, patch check, refusal review, overhead measurement and packet revision |
| Worked examples | A step kind that changes one configuration value, and three harness configurations measured on the wire |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| define-step-kind | agent | Writes a kind: pinned procedure, closed state slice, write scope, observation, grant, allowance and check |
| audit-grant | agent, deterministic | Records what a harness actually sends and flags write-capable tools in read-only kinds |
| assemble-step-packet | agent, deterministic | Builds one step's packet and leaves transcripts out |
| check-patch | agent, deterministic | Admits or rejects returned fields and turns rejections into the next observation |
| review-refusals | agent | Finds refusals without a legal set, repeated answers and the limit that really bound the run |
| measure-step-overhead | agent, deterministic | Measures prefix tokens per configuration and computes the break-even hit rate |
| review-pull-log | agent | Proposes what a kind should receive by default from what its steps fetched and used |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs
instead of enqueueing them. Defects go to [findings to fixes](../findings-to-fixes/README.md);
a task too large for one step goes to [decomposition patterns](../decomposition-patterns/README.md).
Reusing a step's earlier answer is covered by [retrieval triggers and reuse](../retrieval-triggers-and-reuse/README.md).

## Worked examples

All synthetic. The good repair packet carries a rejection that names the two legal field names;
the bad packets each break one rule, such as a read-only step that holds a shell or a slice field
that pastes back the earlier transcript. The measurement shows that with 500 content tokens and
four slices, a configuration sending 8,200 prefix tokens needs a 73.9 percent hit rate to break
even, and one sending 430 still needs 58.1 percent: a cheap prefix lowers the bar but does not
remove it.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Define a step kind before any run uses it.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- The step checks catch missing structure, not a wrong procedure or a slice that omits a needed field.
- The overhead model counts what is sent, not answer quality; whether a cheaper step solves as many tasks is a separate measurement.
- Structural denial depends on the harness; an audit describes one version and configuration only.
