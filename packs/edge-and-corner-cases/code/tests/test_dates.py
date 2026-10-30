"""Each date case holds what its label says. Calendar claims are checked with datetime; daylight saving
claims against the time zone database, for ten years. With EDGE_CASES_REQUIRE_TZDATA=1, as in CI, a
missing database fails instead of skipping."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

from edge_cases import generate
from edge_cases.dates import is_leap, last_sunday, nth_sunday, transitions

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    ZoneInfo("America/New_York")
    TZDATA = None
except (ImportError, ZoneInfoNotFoundError) as exc:  # pragma: no cover - depends on the machine
    TZDATA = str(exc) or "no time zone database"
REQUIRE = os.environ.get("EDGE_CASES_REQUIRE_TZDATA") == "1"


def cases(year: int = 2026) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for case in generate(["dates"], 20261030, {"dates": {"year": year}})["cases"]:
        out.setdefault(case["label"], []).append(case)
    return out


CASES = cases()


def value(label: str) -> str:
    return CASES[label][0]["value"]


def valid(text: str) -> bool:
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def wall(text: str) -> datetime:
    return datetime.fromisoformat(text)


def round_trips(naive: datetime, tz) -> list[tuple[bool, timedelta]]:
    out = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=tz, fold=fold)
        back = aware.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
        out.append((back == naive, aware.utcoffset()))
    return out


class Calendar(unittest.TestCase):
    def test_leap_rules(self) -> None:
        self.assertTrue(valid(value("dates.leap.feb-29")))
        self.assertFalse(valid(value("dates.leap.feb-29-common-year")))
        self.assertFalse(valid(value("dates.leap.century-common")))
        self.assertTrue(valid(value("dates.leap.century-leap")))
        self.assertEqual([is_leap(y) for y in (1900, 2000, 2024, 2026, 2028, 2100)], [False, True, True, False, True, False])
        for year in (2027, 2028, 2100):
            self.assertTrue(valid(cases(year)["dates.leap.feb-29"][0]["value"]), year)

    def test_month_ends(self) -> None:
        self.assertFalse(valid(value("dates.month.day-31-in-30-day-month")))
        self.assertEqual(CASES["dates.month.add-month-to-jan-31"][0]["context"], {"operation": "add one month"})

    def test_iso_weeks(self) -> None:
        last = date.fromisoformat(value("dates.week.iso-week-53"))
        self.assertEqual(last.isocalendar()[1], 53)
        first = date.fromisoformat(value("dates.week.new-year-in-old-week"))
        self.assertEqual(first.isocalendar()[0], first.year - 1, "the ISO week-year is the previous year")
        self.assertEqual(value("dates.format.week-date"), "2026-W44-5")
        self.assertEqual(date.fromisocalendar(2026, 44, 5), date(2026, 10, 30))
        self.assertEqual(value("dates.format.ordinal-date"), "2026-303")

    def test_sundays(self) -> None:
        self.assertEqual(nth_sunday(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(nth_sunday(2026, 11, 1), date(2026, 11, 1))
        self.assertEqual(last_sunday(2026, 3), date(2026, 3, 29))
        self.assertEqual(last_sunday(2026, 10), date(2026, 10, 25))
        self.assertEqual(last_sunday(2026, 12), date(2026, 12, 27))
        for year in range(2026, 2036):
            for day in (nth_sunday(year, 3, 2), last_sunday(year, 10), nth_sunday(year, 4, 1)):
                self.assertEqual(day.weekday(), 6)

    def test_epoch_and_range(self) -> None:
        rollover = datetime.fromisoformat(value("dates.epoch.int32-rollover").replace("Z", "+00:00"))
        self.assertEqual(int(rollover.timestamp()), 2**31)
        before = datetime.fromisoformat(value("dates.epoch.before").replace("Z", "+00:00"))
        self.assertEqual(int(before.timestamp()), -1)
        self.assertTrue(valid(value("dates.range.first-year")))
        self.assertTrue(valid(value("dates.range.last-four-digit-day")))
        self.assertFalse(valid(value("dates.range.five-digit-year")))

    def test_forms_python_refuses_or_reads_differently_by_version(self) -> None:
        with self.assertRaises(ValueError):
            datetime.fromisoformat(value("dates.time.leap-second").replace("Z", "+00:00"))
        end_of_day = value("dates.time.end-of-day-24")
        if sys.version_info < (3, 14):
            with self.assertRaises(ValueError):
                datetime.fromisoformat(end_of_day)
        else:
            self.assertEqual(datetime.fromisoformat(end_of_day), datetime(2026, 10, 31), "read as the next day's 00:00")
        self.assertTrue(value("dates.offset.lowercase-designators").endswith("z"))
        self.assertNotIn(":", value("dates.offset.basic-format")[-5:])


@unittest.skipIf(TZDATA and not REQUIRE, f"no time zone database: {TZDATA}")
class DaylightSaving(unittest.TestCase):
    def setUp(self) -> None:
        if TZDATA:
            self.fail(f"EDGE_CASES_REQUIRE_TZDATA=1 but there is no time zone database: {TZDATA}")

    def test_gaps_never_exist_and_overlaps_exist_twice(self) -> None:
        for label in ("dates.dst.gap-us", "dates.dst.gap-europe", "dates.dst.half-hour-gap",
                      "dates.dst.overlap-us", "dates.dst.overlap-europe", "dates.dst.half-hour-overlap"):
            case = CASES[label][0]
            result = round_trips(wall(case["value"]), ZoneInfo(case["context"]["zone"]))
            if case["context"]["transition"] == "gap":
                self.assertFalse(any(ok for ok, _ in result), label)
            else:
                self.assertTrue(all(ok for ok, _ in result), label)
                self.assertEqual(len({offset for _, offset in result}), 2, label)

    def test_the_rules_match_the_database_for_ten_years_to_the_minute(self) -> None:
        for year in range(2026, 2036):
            for change in transitions(year):
                tz = ZoneInfo(change["zone"])
                day = change["day"]
                start = datetime(day.year, day.month, day.day, *map(int, change["start"].split(":")))
                end = datetime(day.year, day.month, day.day, *map(int, change["end"].split(":")))
                inside = round_trips(start + (end - start) / 2, tz)
                if change["transition"] == "gap":
                    self.assertFalse(any(ok for ok, _ in inside), (year, change))
                else:
                    self.assertTrue(all(ok for ok, _ in inside) and len({o for _, o in inside}) == 2, (year, change))
                for outside in (start - timedelta(minutes=1), end):
                    result = round_trips(outside, tz)
                    self.assertTrue(all(ok for ok, _ in result) and len({o for _, o in result}) == 1, (year, change, outside))

    def test_fixed_offsets_match_their_zones(self) -> None:
        for label, offset in (("dates.offset.half-hour", "+05:30"), ("dates.offset.quarter-hour", "+05:45"),
                              ("dates.offset.plus-fourteen", "+14:00"), ("dates.offset.minus-eleven", "-11:00")):
            case = CASES[label][0]
            moment = datetime.fromisoformat(case["value"])
            self.assertTrue(case["value"].endswith(offset), label)
            self.assertEqual(moment.utcoffset(), moment.astimezone(ZoneInfo(case["context"]["zone"])).utcoffset(), label)

    def test_seeded_times_are_near_a_change(self) -> None:
        for case in generate(["dates"], 99, {"dates": {"seeded": 12}})["cases"]:
            if case["label"] != "dates.seeded.near-transition":
                continue
            moment = wall(case["value"])
            starts = [datetime.combine(c["day"], datetime.strptime(c["start"], "%H:%M").time())
                      for c in transitions(2026) if c["zone"] == case["context"]["zone"]]
            self.assertTrue(any(abs(moment - s) <= timedelta(minutes=90) for s in starts), case["value"])


if __name__ == "__main__":
    unittest.main()
