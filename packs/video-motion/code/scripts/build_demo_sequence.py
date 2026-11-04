"""Regenerate the bundled hackathon demo sequence and its media nouns in examples/sequences/.

The JSON files are the nouns; this script is how they were authored. Scenes are staged in 16:9.
Every actor states its final position and scale for both cuts; the 9:16 layout becomes explicit
per-aspect overrides. The placeholder narration tone, music pad and test-card image are
generated deterministically, so their pins are stable on any machine.
tests/test_video_sequence.py checks that the checked-in files match this script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from video_motion.media import (
    MediaAsset,
    MediaElement,
    MediaGenerator,
    MediaPlacement,
    describe_generated,
    generate_media_bytes,
    media_pin,
)
from video_motion.schemas import (
    AspectOverride,
    AssetAttribution,
    Box2D,
    CaptionCue,
    MotionTrack,
    SceneActor,
    SceneRecipe,
    canonical_sha256,
)
from video_motion.sequence import SceneClip, Transition, VideoSequence
from video_motion.timeline import stage_mapping

FPS = 30
STAGE = "landscape_16x9"
BACKGROUND = "#1b2744"
CARD_FILL = "#0f172a"
SKY, VIOLET, EMERALD, AMBER, WHITE = "#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#f8fafc"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "sequences"
NAME = "hackathon-demo"
DURATION_S = 21.4

# Caption windows (sequence seconds). The narration placeholder tone sounds inside each window.
CAPTIONS = [
    ("cap-01", 0.4, 3.6, "A seed pack turns versioned nouns into video."),
    ("cap-02", 3.9, 7.3, "Scene recipes, media pins and tools are nouns."),
    ("cap-03", 7.6, 10.9, "Render and check are verbs that workers claim."),
    ("cap-04", 11.2, 14.6, "Tessera keeps the leases, versions and receipts."),
    ("cap-05", 15.6, 18.4, "A worker rendered and checked this cut."),
    ("cap-06", 18.7, 21.0, "Narration here is a generated test tone."),
]

Place = tuple[float, float, float]  # x, y, final scale


def _attribution(kind: str) -> AssetAttribution:
    asset_id = f"video-motion-{kind}-primitive"
    definition = {"asset_id": asset_id, "kind": kind, "renderer": "video_motion.timeline"}
    return AssetAttribution(
        asset_id=asset_id,
        license="LicenseRef-Video-Motion-Procedural",
        creator="video-motion vector studio",
        source_uri=f"urn:video-motion:procedural:{kind}",
        sha256=canonical_sha256(definition),
        digest_basis="procedural_definition",
    )


def _track(prop: str, *points: tuple[float, float, str]) -> MotionTrack:
    return MotionTrack.model_validate(
        {"property": prop, "keyframes": [{"t_s": t, "value": v, "easing": e} for t, v, e in points]}
    )


def _appear(start: float, end: float, scale: float, scale_from: float = 0.92) -> list[MotionTrack]:
    """Fade in, spring to `scale` and fill the card's progress bar between `start` and `end`."""
    return [
        _track(
            "opacity",
            (0.0, 0.0, "step_hold"),
            (start, 0.0, "ease_out_cubic"),
            (end, 1.0, "step_hold"),
        ),
        _track(
            "scale",
            (0.0, scale * scale_from, "step_hold"),
            (start, scale * scale_from, "spring_pop"),
            (end, scale, "step_hold"),
        ),
        _track(
            "draw_progress",
            (0.0, 0.0, "step_hold"),
            (start, 0.0, "ease_in_out_cubic"),
            (end, 1.0, "step_hold"),
        ),
    ]


def _actor(
    actor_id: str,
    kind: str,
    label: str,
    size: tuple[float, float],
    accent: str,
    landscape: Place,
    reels: Place,
    tracks: list[MotionTrack],
    *,
    fill: str = CARD_FILL,
    z: int = 10,
    rotate_reels: float = 0.0,
) -> SceneActor:
    """An actor with fixed position on both cuts; `tracks` animate opacity, scale and progress."""
    x, y, scale = landscape
    mapped_x, mapped_y, factor = stage_mapping(x, y, STAGE, "reels_9x16")
    override = AspectOverride(
        dx=round(reels[0] - mapped_x, 3),
        dy=round(reels[1] - mapped_y, 3),
        scale_mul=round(reels[2] / (scale * factor), 4),
        rotation_offset_deg=rotate_reels,
    )
    return SceneActor.model_validate(
        {
            "actor_id": actor_id,
            "kind": kind,
            "label": label,
            "asset_id": f"video-motion-{kind}-primitive",
            "z_index": z,
            "width": size[0],
            "height": size[1],
            "fill_hex": fill,
            "accent_hex": accent,
            "tracks": [
                _track("x", (0.0, x, "linear")).model_dump(),
                _track("y", (0.0, y, "linear")).model_dump(),
                *[t.model_dump() for t in tracks],
            ],
            "aspect_overrides": {"reels_9x16": override.model_dump()},
        }
    )


def _card(
    actor_id: str,
    label: str,
    size: tuple[float, float],
    accent: str,
    landscape: Place,
    reels: Place,
    start: float,
    end: float,
) -> SceneActor:
    return _actor(
        actor_id, "card", label, size, accent, landscape, reels, _appear(start, end, landscape[2])
    )


def _recipe(
    recipe_id: str,
    title: str,
    synopsis: str,
    duration: float,
    beats: list[tuple[str, float, float]],
    actors: list[SceneActor],
) -> SceneRecipe:
    return SceneRecipe.model_validate(
        {
            "recipe_id": recipe_id,
            "title": title,
            "synopsis": synopsis,
            "fps": FPS,
            "duration_s": duration,
            "seed": 2026,
            "stage_aspect": STAGE,
            "background_hex": BACKGROUND,
            "cover_frame_index": round((duration - 0.5) * FPS),
            "beats": [{"phase": p, "start_s": s, "end_s": e} for p, s, e in beats],
            "actors": [a.model_dump() for a in actors],
            "attributions": [
                _attribution(kind).model_dump() for kind in sorted({a.kind for a in actors})
            ],
        }
    )


def title_scene() -> SceneRecipe:
    title = _actor(
        "title",
        "card",
        "VIDEO FROM CODE",
        (520, 150),
        SKY,
        (960, 360, 2.0),
        (474, 600, 1.5),
        [
            _track("opacity", (0.0, 0.35, "ease_out_cubic"), (0.6, 1.0, "step_hold")),
            _track("scale", (0.0, 1.55, "spring_pop"), (0.9, 2.0, "step_hold")),
            _track("draw_progress", (0.0, 0.0, "ease_in_out_cubic"), (1.6, 1.0, "step_hold")),
        ],
        z=20,
    )
    return _recipe(
        "demo-title",
        "Video from nouns and verbs",
        "Title card for the hackathon demo.",
        6.0,
        [("hook", 0.0, 0.8), ("orientation", 0.8, 2.0), ("hold", 2.0, 6.0)],
        [
            title,
            _card(
                "subtitle",
                "Built from nouns, verbs and workers",
                (620, 96),
                VIOLET,
                (960, 590, 1.3),
                (474, 880, 1.25),
                0.6,
                1.4,
            ),
            _card(
                "badge",
                "Made-up motion graphics",
                (480, 80),
                AMBER,
                (960, 735, 1.2),
                (474, 1045, 1.25),
                1.2,
                2.0,
            ),
        ],
    )


def diagram_scene() -> SceneRecipe:
    actors = [
        _card(
            "heading",
            "Nouns → Verbs → Workers",
            (700, 90),
            WHITE,
            (960, 190, 1.2),
            (474, 230, 1.05),
            0.0,
            0.6,
        ),
        _card("nouns", "NOUNS", (330, 110), SKY, (340, 380, 1.3), (474, 370, 1.3), 0.2, 1.0),
        _card("verbs", "VERBS", (330, 110), VIOLET, (960, 380, 1.3), (474, 700, 1.3), 1.6, 2.4),
        _card(
            "workers", "WORKERS", (330, 110), EMERALD, (1580, 380, 1.3), (474, 1030, 1.3), 3.4, 4.2
        ),
        _card(
            "nouns_detail",
            "recipes · media · tools",
            (330, 80),
            SKY,
            (340, 545, 1.15),
            (474, 490, 1.1),
            4.6,
            5.2,
        ),
        _card(
            "verbs_detail",
            "render · check · review",
            (330, 80),
            VIOLET,
            (960, 545, 1.15),
            (474, 820, 1.1),
            5.1,
            5.7,
        ),
        _card(
            "workers_detail",
            "claim · run · submit",
            (330, 80),
            EMERALD,
            (1580, 545, 1.15),
            (474, 1150, 1.1),
            5.6,
            6.2,
        ),
        _card(
            "tessera",
            "Tessera: leases · versions · receipts",
            (760, 100),
            AMBER,
            (960, 740, 1.2),
            (474, 1280, 0.95),
            6.6,
            7.6,
        ),
    ]
    for actor_id, accent, landscape, reels, start, end in (
        ("lane_nv", VIOLET, (650, 380, 1.2), (474, 580, 0.6), 1.0, 2.2),
        ("lane_vw", EMERALD, (1270, 380, 1.2), (474, 910, 0.6), 2.8, 4.0),
    ):
        actors.append(
            _actor(
                actor_id,
                "mechanism",
                "",
                (140, 60),
                accent,
                landscape,
                reels,
                [
                    _track(
                        "opacity",
                        (0.0, 0.0, "step_hold"),
                        (start, 0.0, "ease_out_cubic"),
                        (start + 0.3, 1.0, "step_hold"),
                    ),
                    _track("scale", (0.0, landscape[2], "linear")),
                    _track(
                        "draw_progress",
                        (0.0, 0.0, "step_hold"),
                        (start, 0.0, "ease_in_out_cubic"),
                        (end, 1.0, "step_hold"),
                    ),
                ],
                fill=BACKGROUND,
                z=5,
                rotate_reels=90.0,
            )
        )
    return _recipe(
        "demo-diagram",
        "Nouns, verbs and workers",
        "Animated diagram: nouns feed verbs that authorized workers claim; Tessera supports them.",
        10.0,
        [
            ("hook", 0.0, 0.8),
            ("orientation", 0.8, 2.4),
            ("setup", 2.4, 4.2),
            ("escalation", 4.2, 6.2),
            ("punchline", 6.2, 7.6),
            ("hold", 7.6, 10.0),
        ],
        actors,
    )


SCREEN_BOX_16X9 = Box2D(x=1060.0, y=340.0, width=640.0, height=360.0, label="screen-capture")
SCREEN_BOX_9X16 = Box2D(x=114.0, y=740.0, width=720.0, height=405.0, label="screen-capture")


def outro_scene() -> SceneRecipe:
    return _recipe(
        "demo-outro",
        "Rendered and checked by a worker",
        "Closing card listing the render and QA steps beside a placeholder for a screen capture.",
        6.0,
        [("hook", 0.0, 0.6), ("orientation", 0.6, 1.8), ("setup", 1.8, 3.0), ("hold", 3.0, 6.0)],
        [
            _card(
                "rendered",
                "Rendered and checked by a worker",
                (640, 110),
                EMERALD,
                (960, 210, 1.3),
                (474, 250, 1.2),
                0.0,
                0.6,
            ),
            _card(
                "step_frames",
                "frames → PNG (Chromium)",
                (560, 90),
                SKY,
                (560, 400, 1.2),
                (474, 400, 1.15),
                0.6,
                1.2,
            ),
            _card(
                "step_encode",
                "H.264 + AAC MP4 (FFmpeg)",
                (560, 90),
                VIOLET,
                (560, 530, 1.2),
                (474, 520, 1.15),
                1.2,
                1.8,
            ),
            _card(
                "step_qa",
                "QA: frames · loudness · captions",
                (560, 90),
                AMBER,
                (560, 660, 1.2),
                (474, 640, 1.15),
                1.8,
                2.4,
            ),
            _card(
                "placeholder_label",
                "Placeholder: swap in a screen capture",
                (640, 70),
                WHITE,
                (1380, 760, 1.1),
                (474, 1215, 1.0),
                1.0,
                1.6,
            ),
        ],
    )


def media_assets() -> dict[str, MediaAsset]:
    windows = [[round(start + 0.1, 3), round(end - 0.1, 3)] for _, start, end, _ in CAPTIONS]
    specs: list[tuple[str, str, MediaGenerator, str]] = [
        (
            "narration-placeholder",
            "Placeholder narration tone",
            MediaGenerator(
                tool="video_motion.media:tone_bursts_wav",
                params={"duration_s": DURATION_S, "windows": windows},
            ),
            "Narration is a generated placeholder tone, not a voice.",
        ),
        (
            "music-bed-placeholder",
            "Placeholder music bed",
            MediaGenerator(
                tool="video_motion.media:pad_wav",
                params={"duration_s": DURATION_S, "freqs_hz": [98, 147, 196]},
            ),
            "The music bed is a generated placeholder chord.",
        ),
        (
            "screen-capture-placeholder",
            "Placeholder for a screen capture",
            MediaGenerator(
                tool="video_motion.media:placeholder_card_png", params={"width": 960, "height": 540}
            ),
            "The inset image is a generated test card standing in for a screen capture.",
        ),
    ]
    return {
        media_id: describe_generated(
            media_id=media_id,
            title=title,
            generator=generator,
            disclosure=disclosure,
            payload=generate_media_bytes(generator),
        )
        for media_id, title, generator, disclosure in specs
    }


def _element(asset: MediaAsset, element_id: str, **fields: Any) -> MediaElement:
    return MediaElement.model_validate(
        {
            "element_id": element_id,
            "media": media_pin(asset).model_dump(),
            "blob_sha256": asset.blob_sha256,
            "kind": asset.kind,
            **fields,
        }
    )


def build() -> tuple[VideoSequence, list[MediaAsset]]:
    assets = media_assets()
    overlay = _element(
        assets["screen-capture-placeholder"],
        "outro-screen-capture",
        start_s=0.8,
        duration_s=5.0,
        placements={
            "landscape_16x9": MediaPlacement(
                box=SCREEN_BOX_16X9, keep_out=[SCREEN_BOX_16X9]
            ).model_dump(),
            "reels_9x16": MediaPlacement(
                box=SCREEN_BOX_9X16, keep_out=[SCREEN_BOX_9X16]
            ).model_dump(),
        },
    )
    captions = [
        CaptionCue(
            cue_id=cue_id,
            text=text,
            start_s=start,
            end_s=end,
            anchor="lower_third",
            font_px=42.0,
            max_chars_per_line=30,
        )
        for cue_id, start, end, text in CAPTIONS
    ]
    sequence = VideoSequence.model_validate(
        {
            "sequence_id": NAME,
            "title": "Video from nouns and verbs",
            "synopsis": "A 21.4-second showcase rendered by a worker from a pinned sequence noun: a title card, an animated nouns-to-verbs-to-workers diagram and a closing card.",
            "fps": FPS,
            "outputs": ["landscape_16x9", "reels_9x16"],
            "clips": [
                SceneClip(clip_id="title", recipe=title_scene()).model_dump(),
                SceneClip(
                    clip_id="diagram",
                    recipe=diagram_scene(),
                    transition_in=Transition(kind="crossfade", duration_s=0.6),
                ).model_dump(),
                SceneClip(clip_id="outro", recipe=outro_scene(), overlays=[overlay]).model_dump(),
            ],
            "narration": [
                _element(
                    assets["narration-placeholder"], "narration", duration_s=DURATION_S
                ).model_dump()
            ],
            "music_bed": _element(
                assets["music-bed-placeholder"], "music-bed", duration_s=DURATION_S, gain_db=-6.0
            ).model_dump(),
            "captions": [c.model_dump() for c in captions],
            "disclosures": [
                "Replace the placeholder tone, chord and test card with real narration and screen captures before publishing."
            ],
        }
    )
    return sequence, list(assets.values())


def render_files() -> dict[str, str]:
    sequence, assets = build()
    return {
        f"{NAME}.json": json.dumps(sequence.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        f"{NAME}.media.json": json.dumps(
            {
                "format": "video_motion.media-nouns.v1",
                "assets": [a.model_dump(mode="json") for a in assets],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in render_files().items():
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"wrote examples/sequences/{name}")
