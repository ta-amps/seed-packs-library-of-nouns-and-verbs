# Social cut-downs

## What this pack lets workers do

A collection of nouns and verbs for deriving platform cut-downs from a longer video, approved by a
person before anyone posts them. Workers rank hook moments the long cut already earns, plan the
segments a short cut keeps with a length target per platform, reframe for 9:16 or 1:1 with text at
full size, burn in captions for muted autoplay, check that cutting added no claim and dropped no
qualifier, and draft the title, description, credits, disclosures, hashtags and alt text with a
privacy scan. A person watches each cut-down on a phone, approves or holds it, and posts it
themselves through the platform's own app or site. Workers never post, schedule or hold credentials.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | A person approves and posts; a cut-down only shortens and reframes; labels survive the cut; honest hooks |
| Hook selection rules | Visible change in half a second, a closed list of curiosity devices, no setup needed, a payoff inside |
| Platform targets | Verified, dated facts with their official pages, the rule for unchecked values, and house length defaults |
| Reframe, caption and copy rules | Vertical crops per shot, burned-in caption sizes and places, and what a post's words must and must not say |
| Templates | Platform profile, hook candidates, cut-down plan, meaning check, copy draft, approval |
| Cut-down checks | Seven checks on a cut-down summary, with one good and seven bad summaries the validator recomputes |
| Posting checklist, sources, test cases | What a person does before and after posting; 4 dated sources; 6 made-up cases |
| Worked examples | Made-up: a profile, three ranked hooks, a 33.6-second teaser plan, a meaning check and its copy |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `find-hook-moments` | agent | Rank openings from the long cut's own lines, with devices and payoffs |
| `plan-cutdown` | agent | Segments, order and length for one platform, and the verbs to reframe and compose |
| `check-meaning` | a different agent | New claims, changed claims and dropped qualifiers; passes only when all are empty |
| `draft-copy` | agent | Title, description, credits, disclosures, hashtags and alt text, privacy-scanned |
| `approve-cutdown` | person | Watch on a phone with sound and muted, read the copy, approve or hold |

The flow also uses the [video editing pack](../video-editing/README.md) to reframe, the video and
motion pack to render, the [video QA pack](../video-qa/README.md) for sizes and keep-outs, the
[thumbnails and titles pack](../thumbnail-and-title/README.md) for the cover, and the video showcase
pack's `record-publication` for the person's record of what they posted. Each verb can also end with
`no_change`, `unknown` or `blocked`, and proposes follow-up verbs instead of enqueueing them.

## How to use it

Write the nouns in [nouns.json](nouns.json) create-only with a key scoped to your team's surface, then
fill a template from [verbs.json](verbs.json) with
`scripts/build_packs.py --instantiate <template> --inputs inputs.json --queue <your queue>` and
enqueue the printed task yourself. Workers need keys on the same surface.

## Limits

- A proposal: not installed, imported, admitted or activated, and no worker has claimed these verbs.
- Only YouTube's Shorts length and upload settings were verified, on 2026-10-30. Other platforms'
  limits change often and are left for a person to check on the day; nothing here is a current limit.
- Hook ranking checks a closed list of devices; it does not predict how a post will perform.
- The worked examples are made-up; the library's tests recompute the teaser's length and rescan its
  copy. Sources were checked on 2026-10-30. Recheck them before relying on them.
