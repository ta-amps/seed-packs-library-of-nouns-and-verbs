"""Render the handwritten statements kit's made-up sample pages from its test-case noun.

    uv run python render_samples.py --out DIR [--fonts DIR] [--check]

The page text, marks, font and size of every sample live in the pack's source.json, in the
test-cases noun, so the samples have one source. Each page is drawn on lined paper with an
openly licensed handwriting font, fetched by pinned URL and checked by SHA-256, and stamped
MADE-UP. `--check` compares each page's pixel digest with the digest the noun pins.

Inline marks in a line: {x:word} is drawn crossed out; {?:word} is smudged so it is hard to read.
The output goes only where --out says, never into the library tree. Nothing here contacts a
person, enqueues work or calls a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "source.json"
MARK = re.compile(r"\{([x?]):([^}]+)\}")
WIDTH, HEIGHT = 1000, 1300
PAPER, RULE, MARGIN, INK, STAMP = (250, 248, 240), (190, 205, 230), (230, 160, 160), (30, 42, 110), (200, 30, 40)
TOP, LINE_GAP, LEFT = 170, 62, 110


def load_pages(source: Path = SOURCE) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The font pins and the page specs of the pack's test-cases noun."""
    pack = json.loads(source.read_text(encoding="utf-8"))
    nouns = {noun["slug"]: noun for noun in pack["nouns"]}
    cases = nouns["test-cases"]["value"]["cases"]
    fonts = nouns["sample-renderer"]["value"]["fonts"]
    return fonts, [case["page"] for case in cases if "page" in case]


def default_font_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "kit-handwritten-statements" / "fonts"


def fetch_font(spec: dict[str, Any], cache: Path) -> Path:
    """The pinned font file, downloaded once and always checked against its SHA-256."""
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / spec["file"]
    if not path.exists():
        with urllib.request.urlopen(spec["url"], timeout=60) as response:
            path.write_bytes(response.read())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != spec["sha256"]:
        path.unlink()
        raise ValueError(f"{spec['file']}: SHA-256 {digest} does not match the pinned {spec['sha256']}")
    return path


def plain_text(line: str) -> str:
    return MARK.sub(lambda m: m.group(2), line)


def expected_line(line: str) -> str:
    """How the transcription rules write a line: crossed-out words marked, smudged words flagged."""
    return MARK.sub(lambda m: f"[crossed out: {m.group(2)}]" if m.group(1) == "x" else f"{m.group(2)} [?]", line)


def draw_paper(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    for y in range(TOP + 18, HEIGHT - 40, LINE_GAP):
        draw.line([(40, y), (WIDTH - 40, y)], fill=RULE, width=2)
    draw.line([(LEFT - 30, 40), (LEFT - 30, HEIGHT - 40)], fill=MARGIN, width=2)


def draw_line(image: Image.Image, font: ImageFont.FreeTypeFont, line: str, index: int) -> None:
    draw = ImageDraw.Draw(image)
    x = LEFT + (index * 37) % 9 - 4
    baseline = TOP + index * LINE_GAP
    pos = 0
    for match in [*MARK.finditer(line), None]:
        end = match.start() if match else len(line)
        for word_index, word in enumerate(re.split(r"( )", line[pos:end])):
            if not word:
                continue
            y = baseline + ((index * 13 + word_index * 7) % 5) - 2
            draw.text((x, y), word, font=font, fill=INK, anchor="ls")
            x += draw.textlength(word, font=font)
        if match is None:
            break
        kind, word = match.group(1), match.group(2)
        left, top, right, bottom = draw.textbbox((x, baseline), word, font=font, anchor="ls")
        draw.text((x, baseline), word, font=font, fill=INK, anchor="ls")
        if kind == "x":
            x_top, x_bottom = draw.textbbox((x, baseline), "x", font=font, anchor="ls")[1::2]
            middle = (x_top + x_bottom) // 2
            draw.line([(left - 2, middle + 3), (right + 2, middle - 3)], fill=INK, width=3)
        else:
            box = (int(left) - 4, int(top) - 4, int(right) + 4, int(bottom) + 4)
            image.paste(image.crop(box).filter(ImageFilter.GaussianBlur(radius=4)), box)
        x = right
        pos = match.end()


def draw_stamp(image: Image.Image) -> Image.Image:
    header = ImageFont.load_default(size=22)
    draw = ImageDraw.Draw(image)
    draw.text((LEFT - 14, 40), "MADE-UP SAMPLE: not a real person or statement", font=header, fill=STAMP)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    stamp = ImageDraw.Draw(layer)
    big = ImageFont.load_default(size=150)
    stamp.text((WIDTH // 2, HEIGHT // 2), "MADE-UP", font=big, fill=(*STAMP, 70), anchor="mm")
    layer = layer.rotate(30, resample=Image.Resampling.BICUBIC, center=(WIDTH // 2, HEIGHT // 2))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


def render_page(page: dict[str, Any], font_path: Path) -> Image.Image:
    font = ImageFont.truetype(str(font_path), page["size"])
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw_paper(image)
    for index, line in enumerate(page["lines"]):
        draw_line(image, font, line, index)
    return draw_stamp(image)


def pixel_sha256(image: Image.Image) -> str:
    return hashlib.sha256(f"{image.mode}:{image.size[0]}x{image.size[1]}:".encode() + image.tobytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for the rendered PNG pages")
    parser.add_argument("--fonts", type=Path, default=default_font_cache(), help="font cache folder")
    parser.add_argument("--check", action="store_true", help="fail when a page's pixels differ from its pin")
    args = parser.parse_args(argv)
    if args.out.resolve().is_relative_to(HERE.parents[2].resolve()):
        parser.error("--out must be outside the library tree")
    fonts, pages = load_pages()
    args.out.mkdir(parents=True, exist_ok=True)
    report = []
    for page in pages:
        image = render_page(page, fetch_font(fonts[page["font"]], args.fonts))
        image.save(args.out / page["file"], format="PNG")
        digest = pixel_sha256(image)
        report.append({"file": page["file"], "pixel_sha256": digest, "matches_pin": digest == page.get("pixel_sha256")})
    print(json.dumps({"out": str(args.out), "pages": report}, indent=2))
    if args.check and not all(item["matches_pin"] for item in report):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
