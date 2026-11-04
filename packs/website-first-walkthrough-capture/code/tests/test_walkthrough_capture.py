import copy
import hashlib
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from walkthrough_capture import ZeroHardcodedValuesAstGate, capture_plan, check_storyboard  # noqa: E402

SB = json.loads((HERE / "fixtures" / "storyboard.v3.json").read_text(encoding="utf-8"))


class RealStoryboard(unittest.TestCase):
    def test_v3_storyboard_passes(self):
        self.assertEqual([p for p in check_storyboard(SB) if p[0] == "error"], [])

    def test_capture_plan_uses_the_v6_window(self):
        steps = capture_plan(SB, "film-3m-v6")
        self.assertTrue(steps)
        for st in steps:
            self.assertEqual(st["window_css_px"], [1280, 613])
            self.assertEqual(st["device_scale_factor"], 1.5)
            self.assertTrue(st["take_ids"])
        self.assertIn("#step-split", [st["anchor"] for st in steps])


class Broken(unittest.TestCase):
    def mutate(self, fn):
        sb = copy.deepcopy(SB)
        fn(sb["cuts"][0]["shots"])
        return [p for p in check_storyboard(sb) if p[0] == "error"]

    def test_flash_cut(self):
        def f(shots):
            shots[1]["end"] = shots[1]["start"] + 1.0
        self.assertTrue(self.mutate(f))

    def test_stamp_overlay(self):
        def f(shots):
            shots[3]["on_screen"] = [{"text": "MADE-UP EXAMPLE · typed into the live box", "must_read": False}]
        self.assertTrue(any("stamp" in p[2] for p in self.mutate(f)))

    def test_ken_burns(self):
        def f(shots):
            shots[2]["camera"] = {"scale": 1.03, "drift_px": 12}
        self.assertTrue(any("Ken Burns" in p[2] for p in self.mutate(f)))

    def test_off_site_footage(self):
        def f(shots):
            shots[1]["url"] = "https://example.com/"
        self.assertTrue(any("footage must be on" in p[2] for p in self.mutate(f)))

    def test_credentials_never_in_urls(self):
        def f(shots):
            for s in shots:
                if (s.get("screen_id") or "").startswith("ER-03"):
                    s["url"] = "https://eranos.ta-amps.workers.dev/requests/rq-1?key=abc"
                    break
        self.assertTrue(any("credentials" in p[2] for p in self.mutate(f)))

    def test_request_page_needs_an_anchor(self):
        def f(shots):
            for s in shots:
                if (s.get("screen_id") or "").startswith("ER-03"):
                    s["anchor"] = None
                    break
        self.assertTrue(any("anchor" in p[2] for p in self.mutate(f)))

    def test_retired_name_is_flagged_by_hash(self):
        stand_in = "retired-example-slug"
        sb = copy.deepcopy(SB)
        sb["cuts"][0]["shots"][0]["action"] = f"Open {stand_in} page"
        hashes = frozenset({hashlib.sha256(stand_in.encode("utf-8")).hexdigest()})
        errs = [p for p in check_storyboard(sb, retired_hashes=hashes) if p[0] == "error"]
        self.assertTrue(any("retired name" in p[2] for p in errs))

    def test_zero_hardcoded_values_ast_gate(self):
        res = ZeroHardcodedValuesAstGate.scan_paths(sorted((HERE / "walkthrough_capture").glob("*.py")))
        self.assertEqual(res["violation_count"], 0, res["violations"])


if __name__ == "__main__":
    unittest.main()
