"""Unit tests for rubric_audit."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rubric_audit import (
    DEFAULT_RUBRIC_PILLARS,
    audit_repository_manifest,
    build_manifest_from_directory,
)


def _complete_manifest() -> dict:
    return {
        "repo_id": "synth-multimodal-ops",
        "readme_text": (
            "Field inspection teams face a critical bottleneck reviewing 1,200 drone frames per hour "
            "under 250 ms latency budgets. Operators use this tool to segment defects and align voice notes. "
            "Live app: http://127.0.0.1:8080/health and walkthrough: https://youtu.be/demo12345"
        ),
        "files": [
            "README.md",
            "Dockerfile",
            ".github/workflows/ci.yml",
            "src/pipeline/segmenter.py",
            "src/pipeline/transcriber.py",
            "tests/test_segmenter.py",
        ],
        "code_and_config_blobs": [
            "import sam2\nfrom peft import LoraConfig\nMODEL = 'meta-llama/Llama-3.3-70B'\n"
        ],
        "commits_in_window": 14,
        "commits_outside_window": 0,
        "probe_receipts": [
            {
                "url": "http://127.0.0.1:8080/health",
                "http_status": 200,
                "body_sha256": "a" * 64,
            }
        ],
    }


class RubricAuditTests(unittest.TestCase):
    def test_default_weights_sum_to_100_percent_and_10_points(self) -> None:
        self.assertAlmostEqual(sum(v["weight_pct"] for v in DEFAULT_RUBRIC_PILLARS.values()), 100.0)
        self.assertAlmostEqual(sum(v["max_points"] for v in DEFAULT_RUBRIC_PILLARS.values()), 10.0)

    def test_complete_evidence_backed_repo_scores_full_10_points(self) -> None:
        report = audit_repository_manifest(_complete_manifest())
        self.assertEqual(report["total_points"], 10.0)
        self.assertEqual(report["readiness_tier"], "submission_ready")
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["prioritized_remediations"], [])

    def test_readme_only_model_claims_get_zero_tooling_points_and_blocker(self) -> None:
        man = _complete_manifest()
        man["readme_text"] += " Uses sam2 and meta-llama open weights."
        man["code_and_config_blobs"] = ["print('hello world')\n"]
        report = audit_repository_manifest(man)
        p2 = report["pillar_scores"]["verified_open_weight_and_multimodal_models"]
        self.assertEqual(p2["points"], 0.0)
        self.assertIn("sam_segmentation", p2["unverified_prose_claims"])
        self.assertTrue(any("absent from code" in b for b in report["blockers"]))

    def test_unprobed_live_url_withholds_full_demo_credit(self) -> None:
        man = _complete_manifest()
        man["probe_receipts"] = []
        report = audit_repository_manifest(man)
        p4 = report["pillar_scores"]["live_endpoint_and_video_completeness"]
        self.assertLess(p4["points"], 2.5)
        self.assertTrue(any("HTTP 200" in b for b in report["blockers"]))

    def test_missing_tests_ci_and_dockerfile_ranked_in_remediations(self) -> None:
        man = _complete_manifest()
        man["files"] = ["README.md", "app.py"]
        report = audit_repository_manifest(man)
        p3 = report["pillar_scores"]["modular_source_tests_ci_depth"]
        self.assertLess(p3["points"], 0.5)
        actions = " ".join(r["action"] for r in report["prioritized_remediations"])
        self.assertIn("unit tests", actions)
        self.assertIn("Dockerfile", actions)

    def test_directory_scanner_builds_manifest_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Engineers face a clear problem processing 500 ms audio chunks for field teams with sam2.",
                encoding="utf-8",
            )
            (root / "pkg").mkdir()
            (root / "pkg" / "core.py").write_text("import sam2\n", encoding="utf-8")
            (root / "pkg" / "util.py").write_text("from peft import LoraConfig\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_core.py").write_text("import unittest\n", encoding="utf-8")
            manifest = build_manifest_from_directory(root, commits_in_window=6)
            report = audit_repository_manifest(manifest)
            self.assertEqual(
                report["pillar_scores"]["verified_open_weight_and_multimodal_models"]["points"],
                2.5,
            )

    def test_cli_audit_subcommand(self) -> None:
        code_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            mpath = Path(tmp) / "manifest.json"
            mpath.write_text(json.dumps(_complete_manifest()), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "rubric_audit", "audit", str(mpath)],
                cwd=code_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            parsed = json.loads(proc.stdout)
            self.assertEqual(parsed["total_points"], 10.0)


if __name__ == "__main__":
    unittest.main()
