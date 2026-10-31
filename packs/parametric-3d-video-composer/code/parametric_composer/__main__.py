"""CLI entry point for parametric_composer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .camera import plan_product_hub_trajectory
from .layout import compute_browser_chrome_layout, verify_safe_area_and_caption_band
from .transitions import validate_zero_double_exposure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m parametric_composer")
    sub = parser.add_subparsers(dest="command", required=True)

    tr = sub.add_parser("trajectory", help="plan a 1x3 or 2x2 Product Hub 3D camera trajectory")
    tr.add_argument("--grid", choices=["1x3", "2x2"], default="1x3")

    ch = sub.add_parser("browser", help="compute desktop browser window and tab chrome layout")
    ch.add_argument("--box", nargs=4, type=float, default=[160, 96, 1760, 796])
    ch.add_argument("--tabs", nargs="+", default=["Overview", "Runs", "Evidence"])

    vf = sub.add_parser("verify", help="verify stage safe-area, caption band and transitions from JSON")
    vf.add_argument("--scene-json", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "trajectory":
        print(json.dumps(plan_product_hub_trajectory(grid_mode=args.grid), indent=2, sort_keys=True))
        return 0
    if args.command == "browser":
        print(json.dumps(compute_browser_chrome_layout(args.box, args.tabs), indent=2, sort_keys=True))
        return 0
    if args.command == "verify":
        doc = json.loads(args.scene_json.read_text(encoding="utf-8"))
        layout_res = verify_safe_area_and_caption_band(doc.get("elements", []))
        trans_res = validate_zero_double_exposure(doc.get("shots", []), doc.get("transitions", []))
        print(json.dumps({"layout": layout_res, "transitions": trans_res}, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
