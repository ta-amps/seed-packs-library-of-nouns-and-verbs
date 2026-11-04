"""Noun digests, tool source manifests, license and QA gates, and side-effect-free pure tools."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import video_motion.social
from video_motion.cli import main
from video_motion.errors import BundledDataMissingError, QAGateFailureError, UnlicensedAssetError
from video_motion.nouns import tool_source_manifest, value_sha256
from video_motion.social import (
    CatalogAssetRecord,
    compile_deliverable,
    default_asset_catalog,
    load_bundled_recipes,
)

ROOT = Path(__file__).resolve().parents[1]


def _loaded_files(probe: str) -> set[str]:
    out = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return {
        "video_motion/__init__.py" if name == "video_motion" else name.replace(".", "/") + ".py"
        for name in json.loads(out)
    }


def test_noun_hash_normalizes_numbers_and_rejects_lossy_values() -> None:
    assert value_sha256({"number": 1.0}) == value_sha256({"number": 1})
    assert value_sha256({"number": 10**16}) == value_sha256({"number": 1e16})
    with pytest.raises(ValueError, match="round-trip"):
        value_sha256({"number": 2**53 + 1})
    with pytest.raises(ValueError, match="JSON"):
        value_sha256({"number": float("nan")})


def test_tool_manifest_covers_every_module_the_tool_executes() -> None:
    manifest = tool_source_manifest("video_motion.social")
    assert {"video_motion/__init__.py", "video_motion/errors.py"} <= set(manifest)
    executed = _loaded_files(
        "import json, sys\n"
        "from video_motion.social import compile_deliverable, load_bundled_recipes\n"
        "for recipe in load_bundled_recipes():\n"
        "    compile_deliverable(recipe, require_qa_pass=True)\n"
        "loaded = sorted(m for m in sys.modules if m == 'video_motion' or "
        "m.startswith('video_motion.'))\n"
        "print(json.dumps(loaded))\n"
    )
    assert executed <= set(manifest), executed - set(manifest)


def test_video_tool_manifest_covers_the_worker_modules() -> None:
    manifest = tool_source_manifest("video_motion.video_worker")
    loaded = _loaded_files(
        "import json, sys\n"
        "import video_motion.video_worker\n"
        "from video_motion.sequence import audit_sequence, load_bundled_sequence\n"
        "sequence, _ = load_bundled_sequence('hackathon-demo')\n"
        "audit_sequence(sequence, 'landscape_16x9')\n"
        "print(json.dumps(sorted(m for m in sys.modules if m == 'video_motion' or "
        "m.startswith('video_motion.'))))\n"
    )
    assert loaded <= set(manifest), loaded - set(manifest)
    assert {
        "video_motion/video_worker.py",
        "video_motion/ffmpeg_graph.py",
        "video_motion/media.py",
    } <= loaded


def test_license_and_qa_gates_refuse_unlicensed_assets_and_failed_qa() -> None:
    catalog = default_asset_catalog()
    catalog.register(
        CatalogAssetRecord(
            asset_id="unknown-asset",
            kind="character",
            label="Unknown",
            license="UNKNOWN_RIGHTS",
            creator="Made-up",
            sha256="9" * 64,
        )
    )
    with pytest.raises(UnlicensedAssetError):
        catalog.resolve_verified("unknown-asset")
    recipe = load_bundled_recipes()[0]
    broken = recipe.model_copy(update={"attributions": recipe.attributions[1:]})
    with pytest.raises(QAGateFailureError):
        compile_deliverable(broken, require_qa_pass=True)


def test_missing_bundled_data_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(video_motion.social, "examples_dir", lambda: tmp_path)
    with pytest.raises(BundledDataMissingError):
        load_bundled_recipes()
    assert main(["recipes"]) == 1
    assert json.loads(capsys.readouterr().err)["code"] == "bundled_data_missing"


def test_wheel_ships_bundled_examples_as_package_data() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["force-include"]["examples"] == "video_motion/examples"
    assert (ROOT / "examples" / "sample-motion-trace.json").is_file()


PURE_PROBE = """
import json, sys
blocked = []
def hook(event, args):
    if event.split(".")[0] in {"subprocess", "socket", "urllib", "http", "webbrowser"} or event in {
        "os.system", "os.posix_spawn", "os.fork", "os.forkpty", "os.exec", "os.spawn"
    }:
        blocked.append(event)
sys.addaudithook(hook)
from video_motion.media import media_noun_value
from video_motion.nouns import value_sha256
from video_motion.sequence import audit_sequence, load_bundled_sequence, plan_sequence
from video_motion.social import compile_deliverable, load_bundled_recipes
bundles = {r.recipe_id: compile_deliverable(r, require_qa_pass=True).post_manifest.bundle_sha256
           for r in load_bundled_recipes()}
sequence, assets = load_bundled_sequence("hackathon-demo")
plan = value_sha256(plan_sequence(sequence).model_dump(mode="json"))
audits = {aspect: audit_sequence(sequence, aspect).receipt_sha256 for aspect in sequence.outputs}
media = sorted(value_sha256(media_noun_value(asset)) for asset in assets)
optional = sorted(m for m in ("playwright", "imageio_ffmpeg") if m in sys.modules)
result = {"blocked": blocked, "optional": optional, "bundles": bundles, "plan": plan,
          "audits": audits, "media": media}
sys.stdout.write(json.dumps(result, sort_keys=True))
"""


def test_pure_tools_are_byte_identical_and_side_effect_free_across_environments() -> None:
    outputs = []
    for seed, tz, lang in (("0", "UTC", "C"), ("4242", "Asia/Tokyo", "C.UTF-8")):
        env = {**os.environ, "PYTHONHASHSEED": seed, "TZ": tz, "LANG": lang, "LC_ALL": lang}
        run = subprocess.run(
            [sys.executable, "-c", PURE_PROBE],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(run.stdout)
        assert result["blocked"] == [], result["blocked"]
        assert result["optional"] == []
        outputs.append(run.stdout)
    assert outputs[0] == outputs[1]
