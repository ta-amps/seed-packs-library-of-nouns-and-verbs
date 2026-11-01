# Declarative chart and diagram SVG

## What this pack lets workers do

A collection of nouns and verbs for compiling structured data tables and component message traces
into accessible, self-contained SVG figures (confidence-interval forest plots, zero-anchored
progression bars, and edge-packet sequence diagrams) checked for WCAG contrast and label
collisions. Hand-written or LLM-improvised SVGs frequently overlap text labels, use low-contrast
strokes, omit `<title>` and `<desc>` accessibility tags, or truncate bar baselines misleadingly.
Workers map validated JSON inputs to one of three deterministic layout grammars, compute linearized
sRGB contrast ratios, check pairwise text bounding boxes for collisions, and parse the resulting
XML to guarantee zero scripts or external asset dependencies.

## Nouns

| Noun | What it holds |
| --- | --- |
| Guardrails | Accessible `<title>` and `<desc>` with zero scripts; WCAG 4.5 text and 3.0 mark contrast; zero label collisions |
| Layout and contrast rules | Forest-plot whisker scaling, zero-anchored progression bars, lifeline lanes, and sRGB luminance math |
| Templates | Declarative figure spec, SVG audit receipt, and compiled accessible SVG bundle |
| Contrast fixture | Deterministic WCAG contrast worked check recomputed by `validate_packs.py` |
| Tool card and code | Tested standard-library Python package in [code/](code/README.md) (`diagram_svg`) |
| Sources | 2 dated public sources: W3C SVG 2 specification and W3C WCAG 2.1 contrast guidelines |
| Worked examples | Synthetic edge-packet sequence specification and passing SVG audit receipt |

## Verbs

| Verb | Who | What happens |
| --- | --- | --- |
| `specify-declarative-figure` | agent | Structure a table or message trace into a validated `forest_plot`, `progression_bars`, or `edge_packet_diagram` spec |
| `compile-accessible-svg` | agent, no model | Compile the declarative spec with `diagram_svg` into self-contained XML with `<title>` and `<desc>` |
| `audit-svg-contrast-and-collisions` | agent, no model | Verify XML well-formedness, script absence, WCAG 2.1 contrast ratios, and zero label-box overlaps |
| `revise-colliding-or-faint-layout` | agent | Adjust column spacing, label brevity, or palette hex values when the deterministic audit reports a failure |

Each verb can also end with `no_change`, `unknown`, or `blocked`, and proposes follow-up verbs
instead of enqueueing them.

## Limits

- A proposal: not installed, imported, admitted, or activated, and no worker has run these verbs.
- Text bounding boxes use a conservative proportional character-width model (`0.58 * font_size`),
  not glyph-shaping metrics from a specific desktop font engine.
- Progression bars require non-negative values anchored at zero; signed deltas belong in
  `forest_plot` around an explicit `null_reference`.
