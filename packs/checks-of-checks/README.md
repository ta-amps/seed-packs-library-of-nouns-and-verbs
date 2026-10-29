# Checks of checks

## What this pack lets workers do

Write tests or rubric items for any verb's output, then prove each check works before
anyone relies on it. A check is trusted only when it passes every known-good example
and catches known-bad ones, including deliberate small breakages (mutations) aimed at
it. A check that rejects good work is thrown out; one that catches nothing goes back
for revision.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The trust rule and where good and bad examples should come from |
| Rule types | Seven deterministic rules: present, enum, min_items, each_has, pattern_absent, pattern_present, when |
| Mutation operators | Five deterministic ways to break a good example: delete, clear, set, append_text, delete_item_field |
| Worked example | Synthetic checks for tool-discovery source cards: a wrong check (rejected), a too-weak check (sent back) and six trusted ones. The validator recomputes it |
| Templates | Check suite, example set and check validation |

## Verbs

| Verb | Who | What happens | Produces |
| --- | --- | --- | --- |
| draft-checks | agent | Writes rules and rubric items from an output template | Check suite |
| build-example-set | a different agent | Known-good, known-bad and targeted mutations | Example set |
| validate-checks | agent | Runs everything twice and applies the trust rule; deterministic | Check validation |
| review-checks | different agent or person | Confirms verdicts and judgment-check agreement | Review |

Each verb can also end with `no_change`, `unknown` or `blocked`.

## How to use it

Point `draft-checks` at the template noun that shapes a verb's output (for example
`repo-review.template.finding`), fill it from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate`, and enqueue it yourself after writing the
nouns in [nouns.json](nouns.json).

## Limits

- The rule language is small on purpose. Properties that need judgment become rubric
  items and need two judges or a person to agree before they are trusted.
- The worked example is synthetic; real example sets should come from accepted outputs
  with receipts and sanitized real failures.
