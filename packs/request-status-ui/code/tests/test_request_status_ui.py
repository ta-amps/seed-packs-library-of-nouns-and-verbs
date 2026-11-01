import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from request_status_ui import (  # noqa: E402
    ZeroHardcodedValuesAstGate,
    from_snapshot,
    plain_line,
    reduce,
    replay_schedule,
    validate,
)

SNAP = json.loads((HERE / "fixtures" / "req-intake-07.snapshot.json").read_text(encoding="utf-8"))


def pantry(upto=None, nobody=False, verdict="approved", decision="use"):
    ev = [
        {"seq": 1, "type": "request.received", "request_id": "rq-1", "at": "2026-11-01T18:14:00Z", "data": {}},
        {"seq": 2, "type": "request.split", "request_id": "rq-1", "data": {"parts": [{"title": "Merge people who signed up twice", "lane": "own_files"}, {"title": "Fix phone and email formats", "lane": "own_files"}]}},
        {"seq": 3, "type": "part.queued", "request_id": "rq-1", "data": {"position": 2, "volunteers_online": 0 if nobody else 3}},
        {"seq": 4, "type": "part.claimed", "request_id": "rq-1", "data": {"lease": {"seconds": 1800, "fencing_token": 1}}},
        {"seq": 5, "type": "part.object_made", "request_id": "rq-1", "data": {"object": {"title": "A step-by-step guide"}}},
        {"seq": 6, "type": "part.submitted", "request_id": "rq-1", "data": {}},
        {"seq": 7, "type": "review.claimed", "request_id": "rq-1"},
        {"seq": 8, "type": "review.verdict", "request_id": "rq-1", "data": {"verdict": verdict, "checks": {"passed": 8, "total": 8}}},
        {"seq": 9, "type": "request.ready", "request_id": "rq-1", "data": {"deliverables": [{"kind": "process", "title": "Clean the sheet", "url": "/catalog/k1"}]}},
        {"seq": 10, "type": "person.decision", "request_id": "rq-1", "data": {"decision": decision}},
        {"seq": 11, "type": "library.added", "request_id": "rq-1", "data": {"task_objects": [{"key": "a"}, {"key": "b"}], "tasks": [{"key": "t"}]}},
    ]
    return ev[:upto] if upto else ev


class Reduce(unittest.TestCase):
    def test_waiting_with_nobody_online_is_honest(self):
        m = reduce(pantry(3, nobody=True))
        self.assertEqual(m["pill"]["label"], "Waiting · no volunteer online")
        self.assertTrue(m["bands"]["step-build"]["nobody_online"])
        self.assertEqual(m["live"], "No volunteer is online right now. Your request keeps its place in line.")

    def test_dedicated_worker_fallback_is_announced(self):
        ev = pantry(3)
        ev[2] = dict(ev[2], data={"position": 1, "volunteers_online": 0, "fallback_at": "2026-11-01T18:30:00Z"})
        m = reduce(ev)
        self.assertFalse(m["bands"]["step-build"]["nobody_online"])
        self.assertEqual(m["live"], "Waiting for a volunteer · 1st in line. If none is free by 6:30 PM, one of Eranos's own workers will pick it up.")

    def test_dedicated_worker_is_never_called_a_volunteer(self):
        ev = pantry(4)
        ev[3] = dict(ev[3], actor={"role": "maker", "kind": "eranos_worker", "run_by": "ta-amps team"})
        m = reduce(ev)
        self.assertEqual(m["bands"]["step-build"]["maker_kind"], "eranos_worker")
        self.assertNotIn("volunteer's AI", m["live"])
        self.assertIn("Eranos's own workers", m["live"])

    def test_place_in_line_uses_ordinals(self):
        self.assertEqual(reduce(pantry(3))["live"], "Waiting for a volunteer · 2nd in line.")

    def test_working_then_checked(self):
        self.assertEqual(reduce(pantry(5))["pill"]["label"], "Being made")
        m = reduce(pantry(8))
        self.assertTrue(m["bands"]["step-review"]["done"])
        self.assertEqual(m["live"], "Checked by a different volunteer. All 8 checks passed.")

    def test_sent_back(self):
        m = reduce(pantry(8, verdict="sent_back"))
        self.assertEqual(m["pill"]["label"], "Sent back for fixes")
        self.assertFalse(m["bands"]["step-review"]["done"])

    def test_library_moment(self):
        m = reduce(pantry())
        self.assertEqual(m["library"], {"added": True, "task_objects": 2, "tasks": 1})
        self.assertEqual([t["state"] for t in m["track"]], ["done"] * 6)
        self.assertEqual(m["track"][4]["label"], "Ready for you")

    def test_public_voice_never_says_you(self):
        m = reduce(pantry(), voice="public")
        for s in m["story"]:
            self.assertNotRegex(s["text"], r"\b[Yy]our\b|\b[Yy]ou\b")
        self.assertEqual(m["track"][4]["label"], "Ready")

    def test_refusal_only_when_it_happened(self):
        self.assertFalse(reduce(pantry())["bands"]["step-review"]["refusal"])
        self.assertTrue(reduce(from_snapshot(SNAP))["bands"]["step-review"]["refusal"])


class Snapshot(unittest.TestCase):
    def test_snapshot_maps_to_valid_events(self):
        ev = from_snapshot(SNAP)
        self.assertEqual(validate(ev), [])
        types = [e["type"] for e in ev]
        self.assertEqual(types[:2], ["request.received", "request.split"])
        self.assertIn("review.refused", types)
        m = reduce(ev)
        self.assertEqual(m["bands"]["step-split"]["lanes"].keys(), {"own_files", "public_info"})
        self.assertTrue(m["bands"]["step-ready"]["signoff"])

    def test_plain_view_carries_no_ids_or_hashes(self):
        for s in reduce(from_snapshot(SNAP))["story"]:
            self.assertNotRegex(s["text"], r"[0-9a-f]{12}|volunteer-[ab]|REQ-|KIT-|HTTP|409")


class Replay(unittest.TestCase):
    def test_reading_speed_floor(self):
        for h in replay_schedule(pantry()):
            line = plain_line(pantry()[h["index"]]) or ""
            self.assertGreaterEqual(h["hold_s"], max(2.0, 0.5 + len(line.split()) / 3.0) - 1e-9)

    def test_band_changes_add_scroll_time(self):
        s = replay_schedule(pantry())
        self.assertTrue(any(x["band_changed"] and x["hold_s"] >= 3.0 for x in s))


class Validate(unittest.TestCase):
    def test_catches_bad_sequences(self):
        bad = pantry(3)
        bad[2] = dict(bad[2], seq=1)
        self.assertTrue(validate(bad))
        self.assertTrue(validate([{"seq": 1, "type": "request.teleported", "request_id": "x"}]))
        self.assertTrue(validate([{"seq": 1, "type": "request.received", "request_id": "x", "receipt": {"sha256": "abc"}}]))

    def test_zero_hardcoded_values_ast_gate(self):
        py_files = sorted((HERE / "request_status_ui").glob("*.py"))
        res = ZeroHardcodedValuesAstGate.scan_paths(py_files)
        self.assertEqual(res["violation_count"], 0, res["violations"])


if __name__ == "__main__":
    unittest.main()
