"""The video-motion command line: recipes, QA, motion learning, rendering and the demo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_motion.cli import main as cli_main


def test_cli_commands_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    examples_root = Path(__file__).resolve().parent.parent / "examples"

    assert cli_main(["recipes"]) == 0
    out_recipes = capsys.readouterr().out
    assert "01-pov-role-skit" in out_recipes

    assert cli_main(["qa", str(examples_root / "01-pov-role-skit.json")]) == 0
    qa_json = json.loads(capsys.readouterr().out)
    assert qa_json["passed"] is True

    profile_out = tmp_path / "learned_profile.json"
    assert (
        cli_main(
            ["learn", str(examples_root / "sample-motion-trace.json"), "--out", str(profile_out)]
        )
        == 0
    )
    _ = capsys.readouterr()
    assert profile_out.is_file()

    render_dir = tmp_path / "render_bundle"
    assert (
        cli_main(
            [
                "render",
                str(examples_root / "03-algorithm-race-explainer.json"),
                "--out",
                str(render_dir),
            ]
        )
        == 0
    )
    render_summary = json.loads(capsys.readouterr().out)
    assert render_summary["qa_passed"] is True
    assert (render_dir / "post.json").is_file()

    demo_dir = tmp_path / "demo_bundle"
    assert cli_main(["demo", "--out", str(demo_dir)]) == 0
    demo_summary = json.loads(capsys.readouterr().out)
    assert len(demo_summary["bundled_recipes_verified"]) == 3
    assert demo_summary["motion_learning"]["retargeted_qa_passed"] is True


@pytest.mark.parametrize("retired", ["serve", "seed-pack"])
def test_cli_offers_no_server_or_pack_export(
    retired: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # The HTTP service and the pack exporter were retired: the pack lives in the pack library.
    with pytest.raises(SystemExit) as exit_info:
        cli_main([retired])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
