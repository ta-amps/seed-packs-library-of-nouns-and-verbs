"""Rebuild the pack's synthetic repository at its recorded dates and recompute both scans exactly from source.json."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import gitrepo
from health_checks import BUCKETS, CLASSES, age_todos, find_swallowed

PACK = Path(__file__).resolve().parents[2]
SOURCE = json.loads((PACK / "source.json").read_text(encoding="utf-8"))
NOUNS = {noun["slug"]: noun["value"] for noun in SOURCE["nouns"]}
INPUTS = NOUNS["example.health-inputs"]
TODO_LEVEL = {"fresh": "info", "aging": "info", "stale": "watch", "ancient": "act", "unknown": "watch"}


def status(items: list[dict]) -> str:
    levels = {item["level"] for item in items}
    return "act" if "act" in levels else "watch" if "watch" in levels else "ok"


@unittest.skipIf(not gitrepo.HAVE_GIT and not gitrepo.REQUIRE_GIT, "git is not installed")
class WorkedExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not gitrepo.HAVE_GIT:
            raise AssertionError("HEALTH_CHECKS_REQUIRE_GIT=1 but git is not installed")
        cls.tmp = tempfile.TemporaryDirectory()
        with mock.patch.dict(os.environ, gitrepo.ISOLATED):
            repo = gitrepo.build(Path(cls.tmp.name) / "repo", INPUTS["commits"])
            cls.todos = age_todos(repo, date.fromisoformat(INPUTS["as_of"]))
            cls.swallowed = find_swallowed(repo)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_the_todo_scan_recomputes(self) -> None:
        scan = NOUNS["example.todo-scan"]["instance"]
        items = [{"location": f"{t['path']}:{t['line']}", "measure": f"{t['marker']} age",
                  "value": (f"{t['age_days']} days by git blame, authored {t['authored_on']}, {t['bucket']}" if t["age_days"] is not None
                            else f"unknown: {t['age_reason']}") + ("" if t["has_ref"] else ", no owner or reference"),
                  "level": TODO_LEVEL[t["bucket"]]} for t in self.todos["items"]]
        self.assertEqual(scan["items"], items)
        self.assertEqual(scan["counts"], {**self.todos["counts"], "without_ref": self.todos["without_ref"]})
        self.assertEqual(scan["status"], status(items))
        self.assertTrue(all(t["age_source"] == "git_blame" for t in self.todos["items"]))
        self.assertFalse(any("strings" in t["text"] for t in self.todos["items"]), "a TODO inside a string is not a marker")

    def test_the_swallow_scan_recomputes(self) -> None:
        scan = NOUNS["example.swallow-scan"]["instance"]
        levels = NOUNS["swallow-rules"]["levels"]
        items = [{"location": f"{f['path']}:{f['line']}", "measure": f["class"], "value": f"{f['handler']} {f['body']} in {f['in']}",
                  "level": levels[f["class"]]} for f in self.swallowed["items"]]
        self.assertEqual(scan["items"], items)
        self.assertEqual(scan["counts"], {**self.swallowed["counts"], "files": self.swallowed["files"], "unparsed": 0})
        self.assertEqual(scan["status"], status(items))
        self.assertNotIn("parse_spots", {f["in"] for f in self.swallowed["items"]}, "a handler that raises is left alone")

    def test_the_finding_quotes_the_scan(self) -> None:
        finding = NOUNS["example.finding"]["instance"]
        item = next(f for f in self.swallowed["items"] if f["in"] == "sync_roster")
        measurement = next(e for e in finding["evidence"] if e["kind"] == "measurement")
        self.assertEqual(measurement["location"], f"{item['path']}:{item['line']}-{item['end_line']}")
        self.assertIn(f"{item['handler']} {item['body']} in sync_roster", measurement["detail"])


class RulesMatchTheCode(unittest.TestCase):
    def test_buckets_and_classes_in_the_nouns_are_the_code(self) -> None:
        self.assertEqual(NOUNS["todo-rules"]["buckets"], {name: [low, high] for name, low, high in BUCKETS})
        self.assertEqual(list(NOUNS["swallow-rules"]["classes"]), list(CLASSES))
        self.assertEqual(set(NOUNS["swallow-rules"]["levels"]), set(CLASSES))


if __name__ == "__main__":
    unittest.main()
