"""Recompute this pack's worked example from source.json: the snapshot check, measures, screens, candidates and review."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from chain_measures import check_snapshot, measures, roll_candidates, screen

PACK = Path(__file__).resolve().parents[2]
NOUNS = {n["slug"]: n["value"] for n in json.loads((PACK / "source.json").read_text(encoding="utf-8"))["nouns"]}
REQUEST = NOUNS["example.review-request"]["instance"]
SNAPSHOT = NOUNS["example.chain-snapshot"]["instance"]
HISTORY = NOUNS["example.iv-history"]["instance"]
REVIEW = NOUNS["example.chain-review"]["instance"]
NUMBER = re.compile(r"\d+\.\d+%?")
PERCENT_OF_DECIMAL = {"iv_from_mid", "provider_iv", "current", "low", "high"}


def same(value: object) -> object:
    """The value as JSON would store it."""
    return json.loads(json.dumps(value))


def cite_id(prefix: str, symbol: str) -> str:
    tail = symbol.split(" ")[1]
    return f"{prefix}-{tail[:6]}{tail[6].lower()}{int(tail[7:]) // 1000}"


class WorkedExample(unittest.TestCase):
    def setUp(self) -> None:
        self.measured = measures(REQUEST, SNAPSHOT, HISTORY)
        self.screened = screen(REQUEST, self.measured)
        self.candidates = roll_candidates(REQUEST, self.measured, self.screened)

    def test_the_snapshot_passes_its_check(self) -> None:
        self.assertEqual(check_snapshot(REQUEST, SNAPSHOT, HISTORY), [])
        source = SNAPSHOT["source"]
        self.assertFalse(source["brokerage_connection"])
        self.assertEqual(source["viewers"], "requester_only")
        canonical = json.dumps(SNAPSHOT["contracts"], sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(source["raw_sha256"], hashlib.sha256(canonical).hexdigest())

    def test_measures_screens_and_candidates_are_recomputed_exactly(self) -> None:
        self.assertEqual(same(self.measured), NOUNS["example.chain-measures"]["instance"])
        self.assertEqual(same(self.screened), NOUNS["example.liquidity-screen"]["instance"])
        self.assertEqual(same(self.candidates), NOUNS["example.roll-candidates"]["instance"])

    def test_what_the_example_shows(self) -> None:
        self.assertEqual(self.measured["flag_counts"], {"delta_differs": 1})
        stale = [r["symbol"] for r in self.screened["results"] if "quote_age" in r["failed"]]
        self.assertEqual(stale, ["FERN.X 270115C00045000"])
        self.assertEqual((self.screened["passed"], self.screened["failed"]), (4, 5))
        self.assertEqual(len(self.candidates["same_strike_later_expiry"]) + len(self.candidates["different_strike"]), 8)
        self.assertEqual((self.measured["iv_rank"]["rank"], self.measured["iv_rank"]["percentile"]), (81.5, 62.9))

    def test_every_figure_traces_to_its_row_and_timestamp(self) -> None:
        contracts = {cite_id("m", row["symbol"]): row for row in self.measured["contracts"]}
        groups = self.candidates["same_strike_later_expiry"] + self.candidates["different_strike"]
        candidates = {cite_id("c", item["symbol"]): item for item in groups}
        times = {row["symbol"]: row["quote_time"] for row in self.measured["contracts"]}
        reference = self.candidates["reference"]["symbol"]
        rank = self.measured["iv_rank"]
        for figure in REVIEW["figures"]:
            cite, field = figure["cite"], figure["field"]
            if cite == "u-price":
                row, stamp = self.measured["underlying"], self.measured["underlying"]["quote_time"]
            elif cite in contracts:
                row, stamp = contracts[cite], contracts[cite]["quote_time"]
            elif cite in candidates:
                row = candidates[cite]
                stamp = min(times[row["symbol"]], times[reference])
            else:
                self.assertEqual(cite, "ivr", figure["label"])
                row = rank
                stamp = {"low": rank["low_date"], "high": rank["high_date"]}.get(field, rank["current_date"])
            value = row
            for part in field.split("."):
                value = value[part]
            if figure["unit"] == "percent" and field.split(".")[-1] in PERCENT_OF_DECIMAL:
                value = round(value * 100, 2)
            with self.subTest(figure=figure["label"]):
                self.assertEqual(figure["value"], value)
                self.assertEqual(figure["data_timestamp"], stamp)

    def test_the_review_states_its_data_and_cites_only_what_exists(self) -> None:
        self.assertEqual(REVIEW["notice"], "Not financial advice")
        self.assertEqual(REVIEW["data_as_of"], SNAPSHOT["snapshot_at"])
        self.assertEqual(REVIEW["data_delay_minutes"], SNAPSHOT["source"]["delay_minutes"])
        known = {"u-price", "ivr", "screen", "request"} | {cite_id("m", r["symbol"]) for r in self.measured["contracts"]}
        known |= {cite_id("c", c["symbol"]) for g in ("same_strike_later_expiry", "different_strike") for c in self.candidates[g]}
        for point in REVIEW["points"]:
            self.assertLessEqual(set(point["cites"]), known, point["text"])
        stale = {cite_id("m", r["symbol"]) for r in self.screened["results"] if "quote_age" in r["failed"]}
        self.assertFalse(stale & {f["cite"] for f in REVIEW["figures"]}, "a stale quote is never a figure")

    def test_the_check_counts_every_number(self) -> None:
        check = NOUNS["example.review-check"]["instance"]
        counted = len(REVIEW["figures"]) + sum(len(NUMBER.findall(p["text"])) for p in REVIEW["points"])
        self.assertEqual(check["numbers_checked"], counted)
        self.assertTrue(check["passed"] and not check["problems"])

    def test_the_tool_card_names_this_code(self) -> None:
        card = NOUNS["tool.chain-measures"]
        self.assertEqual(card["code"], {"$code": "options-chain-review"})
        for command in card["commands"]:
            self.assertTrue(re.match(r"python -m chain_measures (check|measures|screen|candidates|iv-rank) ", command))


if __name__ == "__main__":
    unittest.main()
