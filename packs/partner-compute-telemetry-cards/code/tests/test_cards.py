import copy
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from telemetry_cards import ZeroHardcodedValuesAstGate, cards_from_cascade, render_html, status_line, validate  # noqa: E402

CASCADE = json.loads((HERE / "fixtures" / "partner_compute_cascade.sample.json").read_text(encoding="utf-8"))


class FromCascade(unittest.TestCase):
    def test_todays_record_gives_three_offline_cards(self):
        cards = cards_from_cascade(CASCADE)
        self.assertEqual([c["provider"] for c in cards], ["modal", "baseten", "fireworks"])
        for c in cards:
            self.assertEqual(c["mode"], "offline_check")
            self.assertEqual(validate(c), [], c["provider"])
            self.assertNotIn("measured", c)
            self.assertTrue(c["checked"])

    def test_status_line_is_plain(self):
        title, text = status_line(cards_from_cascade(CASCADE)[0])
        self.assertEqual(title, "Last check: offline")
        self.assertIn("nothing has run there", text)

    def test_live_needs_evidence(self):
        rec = copy.deepcopy(CASCADE)
        rec["modal_qlora_and_sandbox"].update({"mode": "live_measured", "live_credentials_present": True})
        card = cards_from_cascade(rec)[0]
        self.assertEqual(card["mode"], "live_run")
        self.assertTrue(any("measured_at" in p for p in validate(card)))
        rec["modal_qlora_and_sandbox"].update({"measured_at": "2026-11-02T15:00:00Z", "provider_request_ids": ["ap-123"], "measured": {"wall_s": 812}})
        self.assertEqual(validate(cards_from_cascade(rec)[0]), [])


class Honesty(unittest.TestCase):
    def test_offline_cards_cannot_carry_numbers(self):
        card = cards_from_cascade(CASCADE)[1]
        card["throughput_tpm"] = 2000000
        self.assertTrue(validate(card))
        card2 = cards_from_cascade(CASCADE)[2]
        card2["credit_usd"] = 100
        self.assertTrue(validate(card2))

    def test_no_stamp_words(self):
        card = cards_from_cascade(CASCADE)[0]
        card["role"] = "PLANNED: training on Modal"
        self.assertTrue(any("stamp" in p for p in validate(card)))


class Render(unittest.TestCase):
    def test_html_has_no_inline_styles_and_is_escaped(self):
        card = cards_from_cascade(CASCADE)[0]
        card["checked"] = ["<script>alert(1)</script>"]
        out = render_html(card)
        self.assertNotIn("style=", out)
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn('class="pc-card pc-offline_check"', out)

    def test_zero_hardcoded_values_ast_gate(self):
        res = ZeroHardcodedValuesAstGate.scan_paths(sorted((HERE / "telemetry_cards").glob("*.py")))
        self.assertEqual(res["violation_count"], 0, res["violations"])


if __name__ == "__main__":
    unittest.main()
