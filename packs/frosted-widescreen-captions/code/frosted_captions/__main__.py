"""Command line: wrap a line, or check a cue list.

  python3 -m frosted_captions wrap "A volunteer's AI picks it up, with tokens they weren't going to use."
  python3 -m frosted_captions check cues.json      # [{"start": 1.0, "end": 3.2, "text": "..."}, ...]
  python3 -m frosted_captions svg "Text" > band.svg
"""
import json
import sys

from .cues import Cue, check
from .geometry import GRID
from .render import band_svg
from .wrap import split_cues, wrap_balanced

SVG_CFG = GRID["svg"]


def main(argv):
    if len(argv) < SVG_CFG["cli_min_args"]:
        print(__doc__)
        return SVG_CFG["cli_usage_exit"]
    cmd, arg = argv[1], argv[SVG_CFG["cli_arg_index"]]
    if cmd == "wrap":
        for cue in split_cues(arg):
            print(" / ".join(wrap_balanced(cue)))
        return 0
    if cmd == "svg":
        print(band_svg(arg))
        return 0
    if cmd == "check":
        with open(arg, encoding="utf-8") as fh:
            cues = [Cue(float(c["start"]), float(c["end"]), c["text"].replace("|", " ")) for c in json.load(fh)]
        problems = check(cues)
        preview_n = SVG_CFG["cli_preview_chars"]
        for sev, i, msg in problems:
            print(f"{sev}: cue {i + 1} ({cues[i].text[:preview_n]}…): {msg}")
        return 1 if any(p[0] == "error" for p in problems) else 0
    print(__doc__)
    return SVG_CFG["cli_usage_exit"]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
