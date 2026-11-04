# Screenshot design review

## What this pack lets workers do

A collection of nouns and verbs for reviewing a user interface screenshot against design rules.
Workers describe a screenshot sent with little or no text before judging it, capture the page at
named widths and themes, measure text size, contrast, cropping, overflow, alignment, spacing and
broken assets from each capture's layout, record every failing check as a finding with its capture
and location, propose a fix verb for each, and have a different worker re-render the same widths and
themes and verify every fix.

It adds the screenshot-first intake, the capture matrix and the measured checks to packs that exist:
findings, fixes, verification and closing come from [findings to fixes](../findings-to-fixes/README.md);
the contrast formula is [visual and 3D rendering](../visual-rendering/README.md)'s worked example;
captures use the Playwright and Chromium cards of [video and motion](../video-motion/README.md); and a
matter of taste becomes a [taste palettes](../taste-palettes/README.md) brief, never a finding.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | New: describe before judging; every finding names its capture and location; a fix is verified at the same widths and themes. Pinned: no personal data |
| Capture matrix | 320, 768 and 1440 CSS px in light and dark by default, a pinned browser, animations off, one pixel per CSS pixel, layout facts from the same render |
| Design rules | Seven measured checks with thresholds and their basis: WCAG 2.2 for contrast and reflow, team defaults for text size and spacing |
| Templates | Review request, screenshot description, capture plan, capture set, layout facts, design check report; findings and verifications use the findings to fixes templates |
| Design finding checks | Ten checks on a recorded finding, with the worked example's seven findings and ten bad ones the validator recomputes |
| Checklist, sources, test cases | What a person checks before trusting a review; 9 dated public sources; 9 made-up cases |
| Worked example | Made-up: a sign-up page in six cells, before and after a fix |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `describe-screenshot` | agent | What the screenshot shows, its exact text and its unknowns; no finding yet |
| `plan-captures` | agent | Every width, theme and state, and the settings that make captures repeatable |
| `capture-screens` | agent, no model | A screenshot and layout facts for every cell, by digest |
| `check-design-rules` | agent, no model | All seven rules in every cell, each with its measurement |
| `record-design-findings` | agent | One located finding per failing rule and element, each with a proposed fix verb |
| `rerender-and-verify` | a different agent, no model | The same cells on the fixed build, every check rerun, a verdict per finding |

Between recording and verifying, the findings to fixes pack's `triage`, `propose-fix` and `fix` run,
and its `close` ends the flow. Each verb can also end with `no_change`, `unknown` or `blocked`, and
can propose follow-up verbs.

## Worked example

All made-up. A phone screenshot with no words is described first: a cut-off button label, a faint
link, a broken logo and a table running off the edge. Captures of the page at three widths and two
themes give 29 failing checks across all seven rules, recorded as seven findings with their cells and
boxes. After a fix, the contrast finding is verified in every dark cell, and the alignment finding
still fails at 1440, so its fix is not verified. The library's tests recompute every check.

## How to use it

Write a review request shaped like `template.review-request`. Write the nouns in [nouns.json](nouns.json)
create-only with a key scoped to your team's surface, then fill a template from [verbs.json](verbs.json)
with `scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has run these verbs.
- The worked example renders nothing: its layout numbers are made up, and its screenshot digests are
  of stand-in strings. The library's tests recompute the checks from those numbers, not from pixels.
- The checks read the layout a browser reports. They cannot judge hierarchy, tone or taste; those go
  to a person through taste palettes.
- Text size and spacing thresholds are team defaults, not WCAG requirements; a request can set others.
- Sources were checked on 2026-10-30. Recheck them before relying on them.
