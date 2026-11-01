# Frosted widescreen captions code

Standard-library Python package for the `frosted-widescreen-captions` seed pack. It reads the canonical frame
contract (`frosted_captions/frame_v6.json`, a copy of `claude-design-film-frame.v6.json`) and provides:

- `wrap_balanced(text)`: one or two lines of at most 42 characters, broken at clauses, then balanced;
- `split_cues(text)`: long narration lines cut into cues that each fit two lines;
- `visible_spans(cues)` and `check(cues)`: lead, linger and bridging (gaps of 0.5 s or less keep the pill on),
  then the v6 checks (lines, characters a second, cue length, reading time 0.5 + words/3);
- `pill_box(lines)`: the pill's box, centered at (960, 1002), inside the 156 px band with 24 px clearance;
- `band_svg(text)`: a deterministic SVG of the band with its pill.

Run `make check`.

Without make (the Makefile could not be written to the shared folder remotely; copy it from any pack in the library):

```bash
python3 -W error -m compileall -q frosted_captions tests
python3 -W error -m unittest discover -s tests -v
```
