# Social video reframe and hooks

## What this pack lets workers do

A collection of nouns and verbs for planning vertical (`9:16`) and square (`1:1`) video cutdowns
from `16:9` product or engineering demos with subject-safe crop trajectories, hook-beat scoring,
caption-band reflow, and claim-preservation gates. Naively center-cropping a widescreen terminal or
UI demo slices off wide tables, jitter-tracks cursor motion, buries captions beneath mobile overlay
chrome, and trims spoken caveats from performance claims. Workers compute velocity-clamped crop
windows with pillarbox fallback on wide regions, rank concrete opening beats ahead of splash
intros, reflow captions into two-line safe bands under reading-speed limits, and block any cutdown
that drops a required qualifier or visual evidence beat.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Never clip critical regions silently; never drop a claim's qualifiers; captions stay inside safe bands |
| Reframe and hook rules | Crop dimensions, deadband stabilization, pan-velocity clamp, hook scoring, and 18 CPS reading cap |
| Templates | Crop trajectory plan, hook beat ranking, caption reflow plan, and checked cutdown plan |
| Record checks | Deterministic checks on cutdown plans with synthetic good and bad fixtures |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`social_reframe`) |
| Sources | 2 dated public sources on WCAG timed-text readability and ITU-R BT.709 HD frame geometry |
| Worked examples | Synthetic 9:16 cutdown plan preserving a benchmark qualifier and safe-zone captions |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `plan-subject-crop-trajectory` | agent, no model | Compute deadband-stabilized, velocity-clamped 9:16 or 1:1 crop keyframes with pillarbox fallback |
| `score-opening-hook-beats` | agent | Rank candidate opening beats and disqualify filler intros or overlong openings |
| `reflow-safe-zone-captions` | agent, no model | Wrap captions to at most two lines inside vertical safe margins under reading-speed caps |
| `audit-claim-preservation` | agent | Verify every retained headline claim keeps all required qualifiers and its evidence timestamp |
| `compile-cutdown-plan` | agent, no model | Combine crop, hook, caption, and claim-gate outputs into one render-ready cutdown plan |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- The planner consumes keyframe bounding boxes and timed transcripts; it does not decode video files
  or invoke external encoders.
- Safe-band fractions approximate common vertical and square mobile chrome; verify final overlays on
  target player dimensions before rendering.
