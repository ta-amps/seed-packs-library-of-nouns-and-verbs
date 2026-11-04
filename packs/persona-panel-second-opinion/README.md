# Persona panel and second opinion

## What this pack lets workers do

A collection of nouns and verbs for getting independent second opinions before a decision, such as a
nonprofit changing how people sign up for a service. One reviewer is one opinion, and reviewers who
read each other, or share the producer's model, tend to agree for the wrong reasons. Workers define
a panel of three to five reviewers, each with a stated perspective from a card, such as the person it
serves, the skeptic or the operator, and each on a model family other than the producer's wherever
one is available. Every reviewer gives a take alone from the same sealed packet, and an independence
check confirms that before anyone reads the views. The synthesis leads with where the reviewers
disagree, quotes each side exactly and says where each disagreement goes next. Someone who wrote none
of it audits the synthesis, and a person decides.

It reuses two packs where they overlap. A disagreement of taste becomes a
[taste palettes](../taste-palettes/README.md) brief, and the views are read in a recorded shuffle as
that pack's method asks. A factual disagreement goes to [evaluation design](../evaluation-design/README.md)
instead of a vote. The person-decides guardrail is the policy and law watch pack's.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Independent takes; disagreement first; other model families where possible; plus the person-decides guardrail |
| Panel rules | Three to five reviewers, roles never real people, the producer off its own panel, opaque reviewer ids |
| Independence rules | One packet, nothing shared, views sealed by digest before reading, a fixed shuffled reading order |
| Synthesis rules | Quoted sides, four kinds of disagreement and their routes, no head counts, no recommendation |
| Perspective cards | The person it serves, the skeptic, the operator, the steward, the newcomer, safety and privacy |
| Templates | Panel, view, independence check, synthesis, synthesis audit and decision |
| Panel checks | 12 deterministic checks with 2 made-up good and 12 made-up bad syntheses, rechecked by `make check` |
| Checklist, test cases, sources | What a person reads before deciding; 7 made-up cases; 4 dated public sources |
| Worked examples | A panel, three sealed views, their independence check, the synthesis, its audit and the decision |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `define-panel` | agent | Perspectives, families, the packet, a deadline and a reading seed |
| `give-view` | one reviewer, agent or person | A stance, points with confidence, what would change its mind |
| `check-independence` | agent, no model | Digests, packets, seal times, exclusions and the reading order |
| `synthesize-disagreements` | a different agent | Each disagreement quoted, typed and routed; nothing decided |
| `audit-synthesis` | a different agent or a person | Quotes rechecked, dropped points, routes, head counts |
| `decide` | person | Proceed, proceed with changes, do not proceed or decide later |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Verbs for a person are claimed by people, never by an agent.

## Worked examples

All made-up: a literacy program's plan, drafted by a model run on family-a, to replace paper
sign-in sheets with tablet check-in at two tutoring sites. Three reviewers take it alone, on
family-b, family-c and family-a, the last labeled with the reason. The views disagree on a fact,
whether check-ins survive one site's evening wifi outages, and on a value, whether quicker check-in
is worth a screen some learners cannot read yet. The program director keeps paper beside the tablet
and leaves the factual question to a week-long test. The library's tests recompute every view's
digest, the reading order from its seed and every quote against its view.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface,
then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Run one give-view verb per reviewer, each as its own attempt.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- Perspective cards are lenses, not people: a panel never replaces asking the people a decision
  affects, and its made-up reviewers speak for no one.
- Reviewers on different model families can still share blind spots, and a same-family reviewer is
  labeled, not excluded. The checks cannot tell how independent two models really are.
- The panel checks catch missing perspectives, seals, quotes and routes, not a wrong judgment; the
  audit and the person's decision still matter.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
