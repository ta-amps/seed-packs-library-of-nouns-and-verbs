# Accessibility checks

Deterministic checks the accessibility audit pack's verbs run inside a claimed verb: WCAG 2.2
contrast ratios for text (1.4.3, with 1.4.6 reported separately) and non-text parts (1.4.11), and a
landmark, heading-order, page-language and page-title lint for one HTML document. Python 3.10 or
later, standard library only.

```bash
make check                                              # compile, then every test
python -m a11y_checks contrast '#767676' '#ffffff' --size-px 16
python -m a11y_checks contrast --pairs pairs.json       # [{"id", "foreground", "background", "size_px", "weight", "kind"}]
python -m a11y_checks structure page.html --strict      # advisories fail too
```

Contrast composites transparent colors over their background, applies the large-text rule (24
CSS pixels, or 18.67 and bold) and decides pass or fail on the unrounded ratio. The linter reads
markup only: run it on a rendered DOM snapshot, and remember that content hidden only by a style
sheet still counts as visible. Every lint result names its criterion and says failure or advisory.

The tests check published reference ratios and every lint rule, and recompute the pack's two worked
examples from [source.json](../source.json). Nothing here renders pages, runs page scripts, calls a
model, opens a network connection or writes a file. MIT license, written for this pack by ta-amps.
