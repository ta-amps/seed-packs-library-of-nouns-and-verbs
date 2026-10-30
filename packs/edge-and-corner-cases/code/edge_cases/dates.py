"""Date and time cases, written as text: leap days, month ends, ISO weeks, local times that daylight
saving skips or repeats, unusual offsets, leap seconds, epoch edges, far years and ambiguous formats.

Daylight saving dates come from the rules in force since 2008, computed by weekday arithmetic, so the
output never depends on the time zone database installed; years before 2008 are refused: United States (second Sunday in March, first Sunday in
November), the United Kingdom and European Union (last Sundays of March and October) and Lord Howe
Island (a half-hour shift on the first Sundays of October and April). The tests check every one of them
against the time zone database.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .case import Case, Spec
from .rng import SplitMix64

KIND = "dates"
DEFAULTS = {"year": 2026, "seeded": 3}
LIMITS = {"year": (2008, 2999), "seeded": (0, 50)}
SUNDAY = 6

S = Spec
SPECS = [
    S("dates.leap.feb-29", "leap", "The 29th of February in a leap year.", "Accept; a year later the same date does not exist."),
    S("dates.leap.feb-29-common-year", "leap", "The 29th of February in a year that is not a leap year.", "Reject with a message; never roll over to the 1st of March."),
    S("dates.leap.century-common", "leap", "2100 is divisible by 4 but is not a leap year.", "Reject the 29th of February 2100."),
    S("dates.leap.century-leap", "leap", "2000 is a leap year because it is divisible by 400.", "Accept the 29th of February 2000."),
    S("dates.month.day-31-in-30-day-month", "month", "The 31st of April does not exist.", "Reject; never roll over to the 1st of May."),
    S("dates.month.add-month-to-jan-31", "month", "Adding one month to the 31st of January.", "End of February by a stated rule, or an error; never the 2nd or 3rd of March."),
    S("dates.week.iso-week-53", "week", "The 31st of December in a year with 53 ISO weeks.", "Week 53 exists; reports by week keep it."),
    S("dates.week.new-year-in-old-week", "week", "The 1st of January that belongs to the previous year's last ISO week.", "The ISO week-year differs from the calendar year; never mix the two."),
    S("dates.dst.gap-us", "dst", "A New York local time that does not exist: clocks jump from 02:00 to 03:00.", "Reject or move forward by a stated rule; never store a time that never happened."),
    S("dates.dst.overlap-us", "dst", "A New York local time that happens twice: clocks fall back from 02:00 to 01:00.", "Ask which one, or record the offset; never pick one silently."),
    S("dates.dst.gap-europe", "dst", "A London local time that does not exist: clocks jump from 01:00 to 02:00.", "Reject or move forward by a stated rule."),
    S("dates.dst.overlap-europe", "dst", "A London local time that happens twice: clocks fall back from 02:00 to 01:00.", "Ask which one, or record the offset."),
    S("dates.dst.half-hour-gap", "dst", "A Lord Howe Island local time skipped by a half-hour shift from 02:00 to 02:30.", "Handle shifts that are not whole hours."),
    S("dates.dst.half-hour-overlap", "dst", "A Lord Howe Island local time repeated when clocks go back from 02:00 to 01:30.", "Handle shifts that are not whole hours."),
    S("dates.offset.half-hour", "offset", "An offset of +05:30.", "Kept exactly; never rounded to a whole hour."),
    S("dates.offset.quarter-hour", "offset", "An offset of +05:45.", "Kept exactly; never rounded to a half or whole hour."),
    S("dates.offset.plus-fourteen", "offset", "An offset of +14:00, the earliest calendar day on Earth.", "Accepted; the local date can be two days ahead of a -11:00 place."),
    S("dates.offset.minus-eleven", "offset", "An offset of -11:00.", "Accepted; the local date can be two days behind a +14:00 place."),
    S("dates.offset.basic-format", "offset", "An offset without a colon, which RFC 3339 does not allow.", "Accept as the same offset or reject with a message; never ignore it."),
    S("dates.offset.explicit-utc", "offset", "+00:00 instead of Z.", "Equal to the same time written with Z."),
    S("dates.offset.lowercase-designators", "offset", "Lowercase t and z, which RFC 3339 allows and many parsers reject.", "Accept or reject on purpose and say which."),
    S("dates.offset.none", "offset", "A date and time with no offset.", "Ask whose local time it is, or apply a stated zone; never assume the server's."),
    S("dates.time.leap-second", "time", "A real leap second, 23:59:60.", "Accept or reject on purpose; never crash."),
    S("dates.time.end-of-day-24", "time", "24:00, an end-of-day form parsers disagree on: some reject it, newer ones read it as the next day's 00:00.", "Reject with a message or read as the next day's 00:00 by a stated rule, the same in every component."),
    S("dates.time.seven-fraction-digits", "time", "Seven digits of fractional seconds.", "Keep or round by a stated rule; never reject a valid time for it."),
    S("dates.epoch.zero", "epoch", "The Unix epoch itself.", "A real date, never treated as missing."),
    S("dates.epoch.before", "epoch", "One second before the Unix epoch.", "Accepted; negative timestamps are valid."),
    S("dates.epoch.int32-rollover", "epoch", "2**31 seconds after the epoch, where 32-bit timestamps overflow.", "Accepted and stored exactly."),
    S("dates.range.first-year", "range", "The first day of year 1.", "Accept or reject by range, with a message."),
    S("dates.range.last-four-digit-day", "range", "The last day a four-digit year can write.", "Accept or reject by range, with a message."),
    S("dates.range.five-digit-year", "range", "A five-digit year.", "Reject with a message; never truncate to four digits."),
    S("dates.format.day-month-ambiguous", "format", "03/04 is the 3rd of April in some places and March 4th in others.", "Reject ambiguous forms, or use the person's locale and show the date back in words."),
    S("dates.format.two-digit-year", "format", "A two-digit year.", "Reject, or expand by a stated window and show the full year back."),
    S("dates.format.date-only", "format", "A date with no time.", "Treat as a calendar date, never as midnight in some zone."),
    S("dates.format.week-date", "format", "An ISO week date.", "Accept on purpose or reject with a message."),
    S("dates.format.ordinal-date", "format", "An ISO ordinal date: year and day of the year.", "Accept on purpose or reject with a message."),
    S("dates.seeded.near-transition", "seeded", "A seeded local time within 90 minutes of a daylight saving change.", "Each one exists once, twice or never, and is handled by the rules above."),
]
BY_LABEL = {spec.label: spec for spec in SPECS}


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(SUNDAY - first.weekday()) % 7 + 7 * (n - 1))


def last_sunday(year: int, month: int) -> date:
    end = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return end - timedelta(days=(end.weekday() - SUNDAY) % 7)


def transitions(year: int) -> list[dict[str, Any]]:
    """Every daylight saving change this module knows for one year: zone, kind, day and the local window."""
    return [
        {"zone": "America/New_York", "transition": "gap", "day": nth_sunday(year, 3, 2), "start": "02:00", "end": "03:00"},
        {"zone": "America/New_York", "transition": "overlap", "day": nth_sunday(year, 11, 1), "start": "01:00", "end": "02:00"},
        {"zone": "Europe/London", "transition": "gap", "day": last_sunday(year, 3), "start": "01:00", "end": "02:00"},
        {"zone": "Europe/London", "transition": "overlap", "day": last_sunday(year, 10), "start": "01:00", "end": "02:00"},
        {"zone": "Australia/Lord_Howe", "transition": "gap", "day": nth_sunday(year, 10, 1), "start": "02:00", "end": "02:30"},
        {"zone": "Australia/Lord_Howe", "transition": "overlap", "day": nth_sunday(year, 4, 1), "start": "01:30", "end": "02:00"},
    ]


def local(day: date, hhmm: str) -> str:
    return f"{day.isoformat()}T{hhmm}:00"


def first_year(year: int, test: Any) -> int:
    while not test(year):
        year += 1
    return year


def iso_week(day: date) -> str:
    y, w, d = day.isocalendar()
    return f"{y}-W{w:02d}-{d}"


def cases(limits: dict[str, Any], rng: SplitMix64) -> list[Case]:
    year = limits["year"]
    leap = first_year(year, is_leap)
    common = first_year(year, lambda y: not is_leap(y))
    long_year = first_year(year, lambda y: date(y, 12, 28).isocalendar()[1] == 53)
    us_gap, us_overlap, eu_gap, eu_overlap, lh_gap, lh_overlap = transitions(year)
    oct30 = date(year, 10, 30)

    def zone(t: dict[str, Any]) -> dict[str, Any]:
        return {"zone": t["zone"], "transition": t["transition"], "window": f"{t['start']} to {t['end']}"}

    fixed: list[tuple[str, str, dict[str, Any]]] = [
        ("dates.leap.feb-29", f"{leap}-02-29", {}),
        ("dates.leap.feb-29-common-year", f"{common}-02-29", {}),
        ("dates.leap.century-common", "2100-02-29", {}),
        ("dates.leap.century-leap", "2000-02-29", {}),
        ("dates.month.day-31-in-30-day-month", f"{year}-04-31", {}),
        ("dates.month.add-month-to-jan-31", f"{year}-01-31", {"operation": "add one month"}),
        ("dates.week.iso-week-53", f"{long_year}-12-31", {"iso_week": iso_week(date(long_year, 12, 31))}),
        ("dates.week.new-year-in-old-week", f"{long_year + 1}-01-01", {"iso_week": iso_week(date(long_year + 1, 1, 1))}),
        ("dates.dst.gap-us", local(us_gap["day"], "02:30"), zone(us_gap)),
        ("dates.dst.overlap-us", local(us_overlap["day"], "01:30"), zone(us_overlap)),
        ("dates.dst.gap-europe", local(eu_gap["day"], "01:30"), zone(eu_gap)),
        ("dates.dst.overlap-europe", local(eu_overlap["day"], "01:30"), zone(eu_overlap)),
        ("dates.dst.half-hour-gap", local(lh_gap["day"], "02:15"), zone(lh_gap)),
        ("dates.dst.half-hour-overlap", local(lh_overlap["day"], "01:45"), zone(lh_overlap)),
        ("dates.offset.half-hour", f"{oct30.isoformat()}T09:00:00+05:30", {"zone": "Asia/Kolkata"}),
        ("dates.offset.quarter-hour", f"{oct30.isoformat()}T09:00:00+05:45", {"zone": "Asia/Kathmandu"}),
        ("dates.offset.plus-fourteen", f"{oct30.isoformat()}T09:00:00+14:00", {"zone": "Pacific/Kiritimati"}),
        ("dates.offset.minus-eleven", f"{oct30.isoformat()}T09:00:00-11:00", {"zone": "Pacific/Pago_Pago"}),
        ("dates.offset.basic-format", f"{oct30.isoformat()}T09:00:00+0530", {}),
        ("dates.offset.explicit-utc", f"{oct30.isoformat()}T09:00:00+00:00", {}),
        ("dates.offset.lowercase-designators", f"{oct30.isoformat()}t09:00:00z", {}),
        ("dates.offset.none", f"{oct30.isoformat()}T09:00:00", {}),
        ("dates.time.leap-second", "2016-12-31T23:59:60Z", {}),
        ("dates.time.end-of-day-24", f"{oct30.isoformat()}T24:00:00", {}),
        ("dates.time.seven-fraction-digits", f"{oct30.isoformat()}T09:00:00.1234567Z", {}),
        ("dates.epoch.zero", "1970-01-01T00:00:00Z", {}),
        ("dates.epoch.before", "1969-12-31T23:59:59Z", {}),
        ("dates.epoch.int32-rollover", "2038-01-19T03:14:08Z", {}),
        ("dates.range.first-year", "0001-01-01", {}),
        ("dates.range.last-four-digit-day", "9999-12-31", {}),
        ("dates.range.five-digit-year", "10000-01-01", {}),
        ("dates.format.day-month-ambiguous", f"03/04/{year}", {}),
        ("dates.format.two-digit-year", f"30/10/{year % 100:02d}", {}),
        ("dates.format.date-only", oct30.isoformat(), {}),
        ("dates.format.week-date", iso_week(oct30), {"same_day_as": oct30.isoformat()}),
        ("dates.format.ordinal-date", f"{year}-{oct30.timetuple().tm_yday:03d}", {"same_day_as": oct30.isoformat()}),
    ]
    out = [Case(KIND, BY_LABEL[label], value, context) for label, value, context in fixed]
    every = transitions(year)
    for _ in range(limits["seeded"]):
        change = rng.choice(every)
        hour, minute = (int(part) for part in change["start"].split(":"))
        moment = datetime(change["day"].year, change["day"].month, change["day"].day, hour, minute)
        moment += timedelta(minutes=rng.between(-90, 90))
        out.append(Case(KIND, BY_LABEL["dates.seeded.near-transition"], moment.isoformat(timespec="seconds"), zone(change)))
    return out
