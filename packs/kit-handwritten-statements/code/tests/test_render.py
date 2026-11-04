"""The sample pages match the pack's test-cases noun, carry the MADE-UP stamp and stay outside the tree."""

from __future__ import annotations

import os
import sys
import urllib.error
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import render_samples as rs

FONTS, PAGES = rs.load_pages()


def font_path(name: str) -> Path:
    try:
        return rs.fetch_font(FONTS[name], rs.default_font_cache())
    except (OSError, urllib.error.URLError) as exc:
        if os.environ.get("KIT_HANDWRITTEN_REQUIRE_FONTS") == "1":
            raise
        pytest.skip(f"font {name} unavailable: {exc}")


def test_every_case_page_is_pinned_and_its_expected_text_follows_the_rules() -> None:
    pack = rs.json.loads(rs.SOURCE.read_text(encoding="utf-8"))
    cases = next(n for n in pack["nouns"] if n["slug"] == "test-cases")["value"]["cases"]
    with_pages = [c for c in cases if "page" in c]
    assert len(with_pages) == len(PAGES) >= 3
    for case in with_pages:
        page = case["page"]
        assert "MADE-UP" in case["sample_input"]
        assert page["font"] in FONTS
        assert len(page.get("pixel_sha256", "")) == 64, page["file"]
        assert case["expected_transcription"] == [rs.expected_line(line) for line in page["lines"]]
    for spec in FONTS.values():
        assert spec["license"] == "OFL-1.1" and spec["url"].startswith(
            "https://raw.githubusercontent.com/google/fonts/"
        )


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p["file"])
def test_each_page_renders_to_its_pinned_pixels(page: dict, tmp_path: Path) -> None:
    image = rs.render_page(page, font_path(page["font"]))
    assert image.size == (rs.WIDTH, rs.HEIGHT)
    assert rs.pixel_sha256(image) == page["pixel_sha256"]
    image.save(tmp_path / page["file"])
    assert (tmp_path / page["file"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_stamp_changes_every_page() -> None:
    page = PAGES[0]
    plain = rs.Image.new("RGB", (rs.WIDTH, rs.HEIGHT), rs.PAPER)
    stamped = rs.draw_stamp(plain.copy())
    assert rs.pixel_sha256(stamped) != rs.pixel_sha256(plain)
    assert page["lines"]


def test_rendering_into_the_library_tree_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        rs.main(["--out", str(HERE / "samples")])
    assert not (HERE / "samples").exists()


def test_a_font_with_the_wrong_digest_is_refused(tmp_path: Path) -> None:
    spec = dict(next(iter(FONTS.values())))
    (tmp_path / spec["file"]).write_bytes(b"not the pinned font")
    with pytest.raises(ValueError, match="does not match"):
        rs.fetch_font(spec, tmp_path)
    assert not (tmp_path / spec["file"]).exists()
