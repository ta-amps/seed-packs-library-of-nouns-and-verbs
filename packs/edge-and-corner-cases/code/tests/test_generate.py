"""The generator as a whole: one fixed order, unique ids, identities that recompute, escapes that round-trip,
limits that fail loudly, and the same output in another process with another hash seed."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from edge_cases import KINDS, LABELS, canonical, case_sha256, cases_sha256, escaped, generate, summary

CODE = Path(__file__).resolve().parents[1]
ALL = generate(KINDS, 20261030)


class Identity(unittest.TestCase):
    def test_ids_are_unique_and_ordered_by_kind(self) -> None:
        ids = [case["id"] for case in ALL["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([case["kind"] for case in ALL["cases"]], sorted((c["kind"] for c in ALL["cases"]), key=KINDS.index))
        self.assertEqual(ALL["count"], len(ALL["cases"]))

    def test_every_digest_recomputes(self) -> None:
        for case in ALL["cases"]:
            self.assertEqual(case["sha256"], case_sha256(case["kind"], case["label"], case["value"], case["context"]), case["id"])
        self.assertEqual(ALL["cases_sha256"], cases_sha256(ALL["cases"]))
        triples = [[c["id"], c["label"], c["sha256"]] for c in ALL["cases"]]
        self.assertEqual(ALL["cases_sha256"], hashlib.sha256(canonical(triples).encode()).hexdigest())

    def test_a_digest_names_one_label_value_and_context(self) -> None:
        seen = {}
        for case in ALL["cases"]:
            identity = (case["kind"], case["label"], json.dumps(case["value"]), json.dumps(case["context"], sort_keys=True))
            self.assertEqual(seen.setdefault(case["sha256"], identity), identity, case["id"])
        zero = generate(["numbers"], 1, {"numbers": {"minimum": 0}})["cases"]
        same = [c for c in zero if c["value"] == "0" and c["context"] == {"minimum": 0, "maximum": 100} and c["group"] != "seeded"]
        self.assertEqual({c["label"] for c in same}, {"numbers.boundary.minimum", "numbers.boundary.zero"})
        self.assertNotEqual(same[0]["sha256"], same[1]["sha256"], "the label is part of the identity")

    def test_escapes_are_ascii_and_round_trip_exactly(self) -> None:
        for case in ALL["cases"]:
            self.assertTrue(case["escaped"].isascii(), case["id"])
            self.assertEqual(json.loads(case["escaped"]), case["value"], case["id"])
        self.assertEqual(escaped("Jose\u0301"), '"Jose\\u0301"')

    def test_every_label_is_described_and_used(self) -> None:
        used = {case["label"] for case in ALL["cases"]}
        self.assertEqual(used, set(LABELS))
        for label, spec in LABELS.items():
            self.assertTrue(label.startswith(spec["kind"] + "."), label)
            self.assertTrue(spec["why"] and spec["expect"], label)

    def test_summary_drops_values_only(self) -> None:
        small = summary(ALL)
        self.assertEqual(small["cases_sha256"], ALL["cases_sha256"])
        self.assertFalse(any("value" in c or "escaped" in c for c in small["cases"]))
        self.assertEqual([c["sha256"] for c in small["cases"]], [c["sha256"] for c in ALL["cases"]])


class Determinism(unittest.TestCase):
    def test_same_seed_same_cases_and_other_seeds_differ_only_in_seeded_cases(self) -> None:
        self.assertEqual(generate(KINDS, 20261030), ALL)
        other = generate(KINDS, 7)
        fixed = lambda result: [c for c in result["cases"] if c["group"] != "seeded"]  # noqa: E731
        self.assertEqual(fixed(other), fixed(ALL))
        self.assertNotEqual(other["cases_sha256"], ALL["cases_sha256"])

    def test_asking_for_fewer_kinds_changes_nothing_else(self) -> None:
        dates_only = generate(["dates"], 20261030)["cases"]
        self.assertEqual(dates_only, [c for c in ALL["cases"] if c["kind"] == "dates"])
        self.assertEqual(generate(["lists", "strings"], 20261030)["kinds"], ["strings", "lists"])

    def test_another_process_and_hash_seed_gives_the_same_digest(self) -> None:
        script = "from edge_cases import KINDS, generate; print(generate(KINDS, 20261030)['cases_sha256'])"
        for seed in ("0", "4242"):
            env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(CODE)}
            out = subprocess.run([sys.executable, "-c", script], cwd=CODE, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(out.stdout.strip(), ALL["cases_sha256"])


class Limits(unittest.TestCase):
    def test_bad_limits_and_kinds_fail_loudly(self) -> None:
        for kinds, limits in ((["strings"], {"strings": {"max_lenght": 5}}), (["strings"], {"strings": {"max_length": 0}}),
                              (["strings"], {"strings": {"max_length": True}}), (["strings"], {"dates": {"year": 2026}}),
                              (["dates"], {"dates": {"year": 2007}}), (["colors"], None), ([], None)):
            with self.subTest(kinds=kinds, limits=limits), self.assertRaises(ValueError):
                generate(kinds, 1, limits)
        with self.assertRaises(ValueError):
            generate(["strings"], -1)

    def test_limits_used_are_reported(self) -> None:
        result = generate(["strings", "numbers"], 3, {"numbers": {"maximum": 9}})
        self.assertEqual(result["limits"], {"strings": {"max_length": 64, "seeded": 3},
                                            "numbers": {"minimum": 0, "maximum": 9, "seeded": 3}})


if __name__ == "__main__":
    unittest.main()
