# Usability heuristics review

## What this pack lets workers do

A collection of nouns and verbs for reviewing a page or app against ten usability heuristics kept
as nouns, paraphrased from Jakob Nielsen's ten heuristics. Several evaluators walk real tasks
independently and record each problem against one heuristic, with a severity from 1 to 4 and its
reasons, a screenshot region as evidence and a proposed fix verb. A deterministic rule combines
their sheets without dropping anything; a worker who evaluated nothing confirms, changes or rejects
each finding; and every confirmed finding gets one fix verb, ranked by severity. A heuristic review
is expert inspection: it complements testing with real people, never replaces it.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle and rules: independent evaluators, real tasks, one heuristic per finding |
| Ten heuristics | One noun each, H1 to H10: what it asks, questions, common violations, fix patterns and related WCAG criteria |
| Severity scale | 1 to 4 from impact, frequency and persistence, mapped to the findings levels |
| Combine rules | When two findings are the same problem, median severity rounded up, spread and disagreement |
| Evidence rules | A screenshot stored by SHA-256 and a region inside it, described in words |
| Heuristic checks | 16 deterministic checks with 2 synthetic good and 16 synthetic bad findings, rechecked by `make check` |
| Templates | Review scope, evaluation sheet, combined findings, finding review and fix plan |
| Worked examples | A scope, one evaluator's sheet, two sheets combined with a disagreement and a fix plan |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| scope-review | agent | Pages, real tasks, personas, widths, themes and at least two evaluators |
| evaluate-against-heuristics | agent, once per evaluator | Walks the tasks alone and records findings with evidence and a fix verb |
| combine-findings | agent, no model | Groups the same problem across sheets and takes the median severity |
| review-findings | a different agent or person | Confirms, changes or rejects each finding and settles disagreements |
| propose-fixes | agent | One fix verb per confirmed finding, ranked by severity |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Fixes go to [findings to fixes](../findings-to-fixes/README.md), choices with no
single right answer to [taste palettes](../taste-palettes/README.md), and accessibility problems to
the [accessibility audit](../accessibility-audit/README.md). A screenshot sent with little or no text,
or a measured layout rule, goes to [screenshot design review](../screenshot-design-review/README.md).

## Worked examples

All synthetic, on a made-up pantry volunteer site. Two evaluators review three tasks at two widths.
A button labeled Engage capacity breaks H2, match with the real world, and is rated 3 by both. A visit
page that drops the site's layout breaks H4, consistency, and is rated 2 and 4, so the combined
severity is 3 with a disagreement for the reviewer. The fix plan routes the button's wording to a
palette comparison and the layout to a repair.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Run evaluate-against-heuristics as separate attempts.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- Heuristics are judgment aids; two careful evaluators can still disagree, which is why disagreements stay visible.
- The checks catch missing and inconsistent fields, not a wrong judgment.
- The heuristics' wording is paraphrased with its source named; the questions and examples are original.
