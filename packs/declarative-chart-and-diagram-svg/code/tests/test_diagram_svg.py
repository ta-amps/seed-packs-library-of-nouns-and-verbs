"""Unit tests for diagram_svg (standard library only)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from diagram_svg import (
    DEFAULT_PALETTE,
    audit_svg_document,
    compile_diagram,
    contrast_ratio,
    detect_label_collisions,
)


class DiagramSvgTests(unittest.TestCase):
    def test_wcag_contrast_ratios_match_standard_values(self) -> None:
        self.assertEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0)
        self.assertEqual(contrast_ratio("#FFFFFF", "#FFFFFF"), 1.0)
        self.assertGreaterEqual(contrast_ratio(DEFAULT_PALETTE["text"], DEFAULT_PALETTE["background"]), 15.0)

    def test_forest_plot_compiles_clean_accessible_svg(self) -> None:
        spec = {
            "chart_kind": "forest_plot",
            "title": "Latency Delta by Worker Config (ms)",
            "null_reference": 0.0,
            "rows": [
                {"label": "Baseline pool", "estimate": 0.0, "ci_low": -2.4, "ci_high": 2.4},
                {"label": "Pinned prefix", "estimate": -14.2, "ci_low": -18.0, "ci_high": -10.5},
                {"label": "Bounded retry", "estimate": -6.8, "ci_low": -10.1, "ci_high": -3.2},
            ],
        }
        res = compile_diagram(spec)
        self.assertTrue(res["audit"]["passed"])
        self.assertEqual(res["audit"]["label_collisions"], [])
        self.assertIn('role="img"', res["svg"])

    def test_progression_bars_compile_and_reject_negative_values(self) -> None:
        spec = {
            "chart_kind": "progression_bars",
            "title": "Check Pass Rate Across Waves",
            "unit": "%",
            "target_threshold": 95.0,
            "bars": [
                {"label": "Wave 1 pilot", "value": 70.0},
                {"label": "Wave 2 schema fix", "value": 90.0},
                {"label": "Wave 3 unclamped", "value": 100.0},
            ],
        }
        res = compile_diagram(spec)
        self.assertTrue(res["audit"]["passed"])
        with self.assertRaises(ValueError):
            compile_diagram({"chart_kind": "progression_bars", "bars": [{"label": "bad", "value": -5}]})

    def test_edge_packet_diagram_compiles_without_collisions(self) -> None:
        spec = {
            "chart_kind": "edge_packet_diagram",
            "title": "Lease Claim and CAS Write Sequence",
            "nodes": [
                {"id": "worker", "label": "Worker"},
                {"id": "queue", "label": "Task Queue"},
                {"id": "store", "label": "CAS Store"},
            ],
            "packets": [
                {"from": "worker", "to": "queue", "label": "1. claim(lease)"},
                {"from": "worker", "to": "store", "label": "2. put(v=0)"},
                {"from": "store", "to": "worker", "label": "3. conflict(409)", "status": "error"},
                {"from": "worker", "to": "queue", "label": "4. submit(report)"},
            ],
        }
        res = compile_diagram(spec)
        self.assertTrue(res["audit"]["passed"])
        self.assertEqual(res["audit"]["label_collisions"], [])

    def test_low_contrast_palette_fails_audit(self) -> None:
        spec = {
            "chart_kind": "progression_bars",
            "title": "Unreadable Light Gray Text",
            "palette": {"text": "#D0D0D0", "background": "#FFFFFF"},
            "bars": [{"label": "Row A", "value": 12}],
        }
        res = compile_diagram(spec)
        self.assertFalse(res["audit"]["passed"])
        self.assertFalse(res["audit"]["wcag_contrast"]["text_vs_background"]["passes_aa_4_5"])

    def test_script_element_rejected_by_static_safety_audit(self) -> None:
        malicious = (
            '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="t d">'
            '<title id="t">T</title><desc id="d">D</desc><script>alert(1)</script></svg>'
        )
        audit = audit_svg_document(malicious, DEFAULT_PALETTE, [])
        self.assertFalse(audit["passed"])
        self.assertIn("script", audit["static_safety"]["forbidden_elements"])

    def test_label_collision_detector_catches_overlapping_boxes(self) -> None:
        boxes = [
            {"text": "Alpha", "x": 20.0, "y": 20.0, "width": 50.0, "height": 14.0},
            {"text": "Beta", "x": 45.0, "y": 22.0, "width": 50.0, "height": 14.0},
        ]
        collisions = detect_label_collisions(boxes)
        self.assertEqual(len(collisions), 1)

    def test_cli_render_and_byte_determinism(self) -> None:
        spec = {
            "chart_kind": "progression_bars",
            "title": "Deterministic CLI Check",
            "bars": [{"label": "Step A", "value": 42}],
        }
        a = compile_diagram(spec)
        b = compile_diagram(spec)
        self.assertEqual(a, b)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "chart.json"
            p.write_text(json.dumps(spec), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "diagram_svg", "render", str(p), "--audit-json"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout), a)


if __name__ == "__main__":
    unittest.main()
