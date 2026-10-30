# Accessibility audit

## What this pack lets workers do

A collection of nouns and verbs for auditing a web page or app against WCAG 2.2 level AA. Workers
plan the pages, states, widths, themes and input modes; capture every state read-only; and check
contrast, landmarks and headings, keyboard paths with focus order and visibility, reflow at 320 CSS
pixels, text spacing, target size, captions and transcripts, motion with reduced motion and text
alternatives. A person tries the key tasks with assistive technology. The report gives every finding
its success criterion's number, name and level, says failure or advisory, and states what was not
checked; it never calls a site compliant. The pack ships tested standard-library code for contrast
ratios and for landmark, heading-order and page-language lint.

## Nouns

| Noun | What it holds |
| --- | --- |
| Method | The lifecycle, the citation and evidence rules, severity and how the report's statement is derived |
| WCAG 2.2 source | The W3C Recommendation, its Understanding documents and what changed in 2.2, linked, never copied |
| Checklist | 43 A and AA criteria by area, each with what to check and whether a tool, a person or both decide |
| Capture matrix | Widths 1440, 390 and 320, every theme, both motion settings, pointer and keyboard |
| Keyboard procedure | Per-stop evidence, skip links, traps, Escape and single-key shortcuts |
| Contrast method, layout rules, media and motion rules | How to measure contrast, reflow, text spacing, target size, captions, description and motion |
| Structure rules | The linter's 15 rules, each with its criterion and failure or advisory, kept equal to the code by its tests |
| Tool card | The tested code in [code/](code/README.md), pinned by digest |
| Audit checks | 18 deterministic checks with 4 synthetic good and 18 synthetic bad findings, rechecked by `make check` |
| Templates and worked examples | Plan, capture set, check result, assistive-technology session, report and review, with a plan, a keyboard walk and a report |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| plan-audit | agent | Names pages, states, cells, criteria in scope and what is out of scope |
| capture-states | agent, no model | Read-only screenshots and DOM snapshots of every cell, by digest |
| check-contrast | agent, no model | Ratios in every theme with the contrast tool, citing 1.4.3 or 1.4.11 |
| lint-structure | agent, no model | Landmarks, headings, language and title with the linter |
| walk-keyboard | agent | Every focus stop: visible, not obscured, in order; skip link, traps and shortcuts |
| check-reflow | agent, no model | 320 CSS pixels, wider text spacing and 200 percent text |
| check-target-size | agent, no model | 24 by 24 pixels or a named exception |
| check-media | agent | Captions, description or a media alternative, controls and sound |
| check-motion | agent, no model | Reduced motion on and off, pause controls, flashes left to a tool |
| check-text-alternatives | agent | Names for images, icons, controls and fields |
| check-with-assistive-tech | person | Key tasks with a screen reader, in the tester's words |
| write-audit-report | agent | Cited findings, a criteria summary, what was not checked and a derived statement |
| review-audit | a different agent or person | Reproduces a sample and checks the citations |

Each verb can also end with `no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead
of enqueueing them. Failures go to [findings to fixes](../findings-to-fixes/README.md). Kit documents
are checked by [public-good kits](../public-good-kits/README.md); this pack covers pages and apps.
Measured design rules such as cropping, alignment and spacing belong to
[screenshot design review](../screenshot-design-review/README.md).

## Worked examples

All synthetic. Seven theme colors are measured in both themes; muted gray passes on white at 4.83:1
and fails on the dark background at 3.69:1. Five small pages show what the linter reports, including
a broken skip link on a valid Spanish page. A keyboard walk finds 14 shift buttons with no visible
focus and does not call native video controls a trap. The report carries two failures and one AAA
advisory, and its statement is failures_found because a screen reader session is still to come.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface,
then fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Run the code with `make check` in `code/`.

## Limits

- These are proposals. Nothing here is installed, imported or activated, and no worker has run these verbs.
- Automated checks find only part of what an audit needs; the report says what a person still has to check.
- The linter reads markup, not style sheets, so content hidden only by CSS counts as visible.
- Flashing, caption accuracy and whether narration covers the visuals need a tool or a person, not this code.
