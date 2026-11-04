"""Sequence planning, pre-render QA, pinned media and deterministic placeholder media (pure)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from video_motion.media import (
    LocalMediaLibrary,
    MediaAsset,
    MediaPinError,
    asset_from_noun_value,
    deterministic_sin_turns,
    generate_media_bytes,
    materialize_generated,
    media_noun_value,
    media_pin,
)
from video_motion.nouns import value_sha256
from video_motion.schemas import Box2D, CaptionCue
from video_motion.sequence import (
    SequenceError,
    VideoSequence,
    audit_sequence,
    load_bundled_sequence,
    plan_sequence,
    static_windows,
    with_media_store,
)

ROOT = Path(__file__).resolve().parents[1]


def _demo() -> tuple[VideoSequence, list[MediaAsset]]:
    return load_bundled_sequence("hackathon-demo")


def _with(sequence: VideoSequence, **changes: Any) -> dict[str, Any]:
    return {**sequence.model_dump(mode="json"), **changes}


def test_bundled_demo_matches_its_builder_script() -> None:
    spec = importlib.util.spec_from_file_location(
        "build_demo", ROOT / "scripts/build_demo_sequence.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, text in module.render_files().items():
        assert (ROOT / "examples" / "sequences" / name).read_text(encoding="utf-8") == text


def test_plan_lays_out_cuts_crossfades_and_tracks_on_exact_frames() -> None:
    sequence, _ = _demo()
    plan = plan_sequence(sequence)
    assert [(c.clip_id, c.start_frame, c.frame_count) for c in plan.clips] == [
        ("title", 0, 180),
        ("diagram", 162, 300),
        ("outro", 462, 180),
    ]
    assert plan.total_frames == 642 and plan.duration_s == 21.4
    assert plan.clips[1].transition_in == "crossfade" and plan.clips[1].transition_frames == 18
    assert plan.sources(170) == [("title", 170), ("diagram", 8)] and plan.in_transition(170)
    assert plan.sources(462) == [("outro", 0)]
    assert [(o.start_frame, o.end_frame) for o in plan.overlays] == [(486, 636)]
    assert plan.narration[0].end_frame == 642 and plan.music is not None
    assert plan == plan_sequence(VideoSequence.model_validate(sequence.model_dump(mode="json")))


def test_sequence_validation_rejects_impossible_timelines() -> None:
    sequence, _ = _demo()
    clips = sequence.model_dump(mode="json")["clips"]
    first_crossfade = [
        {**clips[0], "transition_in": {"kind": "crossfade", "duration_s": 0.5}},
        *clips[1:],
    ]
    with pytest.raises(ValidationError, match="crossfade from nothing"):
        VideoSequence.model_validate(_with(sequence, clips=first_crossfade))
    long_fade = [
        clips[0],
        {**clips[1], "transition_in": {"kind": "crossfade", "duration_s": 4.0}},
        clips[2],
    ]
    with pytest.raises(SequenceError, match="crossfade"):
        plan_sequence(VideoSequence.model_validate(_with(sequence, clips=long_fade)))
    with pytest.raises(ValidationError, match="recipe fps"):
        VideoSequence.model_validate(_with(sequence, fps=24))
    late = [*sequence.model_dump(mode="json")["captions"]]
    late[-1] = {**late[-1], "end_s": 30.0}
    with pytest.raises(SequenceError, match="inside the"):
        plan_sequence(VideoSequence.model_validate(_with(sequence, captions=late)))
    unsafe = [{**late[0], "cue_id": "../escape"}, *late[1:-1]]
    with pytest.raises(ValidationError, match="cue_id"):
        VideoSequence.model_validate(_with(sequence, captions=unsafe))
    image_as_music = {
        **sequence.model_dump(mode="json")["clips"][2]["overlays"][0],
        "element_id": "image-as-music",
    }
    with pytest.raises(ValidationError, match="must be audio"):
        VideoSequence.model_validate(_with(sequence, music_bed=image_as_music))


def test_prerender_qa_catches_caption_problems_on_both_cuts() -> None:
    sequence, _ = _demo()
    for aspect in sequence.outputs:
        assert audit_sequence(sequence, aspect).passed
    captions = sequence.model_dump(mode="json")["captions"]
    fast = [{**captions[0], "end_s": 0.9}, *captions[1:]]
    blink = [captions[0], {**captions[1], "start_s": captions[0]["end_s"] + 1 / 30}, *captions[2:]]
    overlap = [captions[0], {**captions[1], "start_s": captions[0]["start_s"] + 1.0}, *captions[2:]]
    covered = [*captions[:4], {**captions[4], "anchor": "center_stage"}, captions[5]]
    cases = {
        "caption_readability": fast,
        "caption_overlap": overlap,
        "caption_media_keep_out": covered,
    }
    for check, cues in cases.items():
        report = audit_sequence(
            VideoSequence.model_validate(_with(sequence, captions=cues)), "landscape_16x9"
        )
        assert not report.passed and not report.checks[check], (check, report.findings)
    blinked = audit_sequence(
        VideoSequence.model_validate(_with(sequence, captions=blink)), "reels_9x16"
    )
    assert any("blink gap" in f.detail for f in blinked.findings)
    tiny = [{**captions[0], "font_px": 20.0}, *captions[1:]]
    assert not audit_sequence(
        VideoSequence.model_validate(_with(sequence, captions=tiny)), "reels_9x16"
    ).passed
    high = CaptionCue(cue_id="x", text="Top", start_s=1.0, end_s=3.0, anchor="top_banner")
    box = high.model_copy(
        update={"box_override": {"reels_9x16": Box2D(x=0.0, y=0.0, width=400.0, height=90.0)}}
    )
    report = audit_sequence(
        VideoSequence.model_validate(_with(sequence, captions=[box.model_dump(mode="json")])),
        "reels_9x16",
    )
    assert not report.checks["caption_safe_zone"]


def test_static_windows_mark_planned_holds_only() -> None:
    sequence, _ = _demo()
    plan = plan_sequence(sequence)
    holds = static_windows(sequence, plan, "landscape_16x9")
    assert holds, "the demo has intended holds"
    for hold in holds:
        assert not any(plan.in_transition(f) for f in range(hold.start_frame, hold.end_frame))
    assert any(
        h.start_frame <= 561 and h.end_frame >= 630 for h in holds
    )  # last caption over a held outro


def test_media_pins_bind_value_digest_bytes_and_kind(tmp_path: Path) -> None:
    sequence, assets = _demo()
    library = materialize_generated(assets, tmp_path / "library")
    for element in sequence.media_elements():
        asset, path = library.resolve(element)
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == element.blob_sha256
            == asset.blob_sha256
        )
        assert element.media == media_pin(asset)
    narration = sequence.narration[0]
    entry = next(e for e in library.entries() if e.pin == narration.media)
    path = tmp_path / "library" / entry.path
    original = path.read_bytes()
    path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(MediaPinError, match="bytes do not match"):
        library.resolve(narration)
    path.write_bytes(original)
    stale = narration.model_copy(
        update={"media": narration.media.model_copy(update={"value_sha256": "0" * 64})}
    )
    with pytest.raises(MediaPinError, match=r"not available|digest"):
        library.resolve(stale)
    wrong_kind = narration.model_copy(update={"kind": "image", "duration_s": 1.0})
    with pytest.raises(MediaPinError, match="is audio"):
        library.resolve(wrong_kind)
    tampered_value = {**entry.value, "title": "changed"}
    forged = LocalMediaLibrary(
        tmp_path / "library", [entry.model_copy(update={"value": tampered_value})]
    )
    with pytest.raises(MediaPinError, match="digest"):
        forged.resolve(narration)
    library.write_index(tmp_path / "library" / "index.json")
    reloaded = LocalMediaLibrary.load(tmp_path / "library" / "index.json")
    assert reloaded.resolve(narration)[0] == asset_from_noun_value(entry.value)


def test_generated_media_are_reproducible_and_labeled() -> None:
    _, assets = _demo()
    for asset in assets:
        assert asset.provenance == "generated" and asset.made_up and asset.disclosure
        assert asset.license == "LicenseRef-Video-Motion-Procedural"
        assert asset.generator is not None
        payload = generate_media_bytes(asset.generator)
        assert hashlib.sha256(payload).hexdigest() == asset.blob_sha256
        assert len(payload) == asset.byte_size
        value = media_noun_value(asset)
        assert asset_from_noun_value(value) == asset
        assert value["category_id"] == "noun.scene_recipe" and value["role"] == "media_asset"
    worst = max(
        abs(deterministic_sin_turns(i / 997) - math.sin(2 * math.pi * i / 997)) for i in range(997)
    )
    assert worst < 1e-8
    with pytest.raises(ValidationError, match="generator"):
        MediaAsset.model_validate({**assets[0].model_dump(mode="json"), "generator": None})
    with pytest.raises(ValidationError, match="made-up"):
        MediaAsset.model_validate({**assets[0].model_dump(mode="json"), "made-up": False})


def test_media_store_retargeting_keeps_keys_and_digests() -> None:
    sequence, _ = _demo()
    moved = with_media_store(sequence, "team.media")
    for before, after in zip(sequence.media_elements(), moved.media_elements(), strict=True):
        assert after.media.store == "team.media"
        assert (after.media.key, after.media.value_sha256) == (
            before.media.key,
            before.media.value_sha256,
        )
    assert json.dumps(moved.model_dump(mode="json")).count('"team.media"') == len(
        sequence.media_elements()
    )
    assert value_sha256(sequence.model_dump(mode="json")) != value_sha256(
        moved.model_dump(mode="json")
    )


IMPORT_PROBE = """
import importlib, importlib.abc, json, pkgutil, sys

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {"playwright", "imageio_ffmpeg"}:
            raise ImportError(f"blocked optional dependency {name}")
        return None

sys.meta_path.insert(0, Block())
import video_motion
names = sorted(m.name for m in pkgutil.iter_modules(video_motion.__path__, "video_motion."))
for name in names:
    importlib.import_module(name)
from video_motion.sequence import audit_sequence, load_bundled_sequence
sequence, _ = load_bundled_sequence("hackathon-demo")
assert audit_sequence(sequence, "reels_9x16").passed
print(json.dumps(names))
"""


def test_every_module_imports_without_the_video_extra() -> None:
    import subprocess
    import sys

    run = subprocess.run(
        [sys.executable, "-c", IMPORT_PROBE], cwd=ROOT, capture_output=True, text=True, check=True
    )
    names = json.loads(run.stdout)
    assert {
        "video_motion.video_worker",
        "video_motion.sequence",
        "video_motion.media",
        "video_motion.cli",
    } <= set(names)
