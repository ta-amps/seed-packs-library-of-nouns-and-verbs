# Checks of checks

## What this pack lets workers do

A collection of nouns and verbs for proving a test or rubric works before anyone relies
on it. A check is trusted only when it passes every known-good example and catches
known-bad ones, including small deliberate breakages (mutations) aimed at it. A check
that rejects good work is thrown out; one that misses what it was aimed at goes back
for revision.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The trust rule and where good and bad examples should come from |
| Rule types | Eight deterministic rules: present, enum, min_items, each_has, pattern_absent, pattern_present, when, hosts_local_only |
| Mutation operators | Five deterministic ways to break a good example: delete, clear, set, append_text, delete_item_field |
| Worked example | Made-up checks for source cards: a wrong check (rejected), a too-weak check (sent back) and six trusted ones |
| Templates | Check suite, example set and check validation |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| draft-checks | agent | Writes rules and rubric items from an output template |
| build-example-set | a different agent | Known-good, known-bad and targeted mutations |
| validate-checks | agent | Runs everything twice and applies the trust rule; deterministic |
| review-checks | different agent or person | Confirms verdicts and judgment-check agreement |

Each verb can also end with `no_change`, `unknown` or `blocked`, and can propose
follow-up verbs, such as revising a weak check.

## How to use it

Point `draft-checks` at the template noun that shapes a verb's output, for example the
repository review pack's finding template. Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's
surface, then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>`
and enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- The rule language is small on purpose. Properties that need judgment become rubric
  items and need two judges or a person to agree before they are trusted.
- The worked example is made-up; real example sets should come from accepted outputs
  with receipts and sanitized real failures.
