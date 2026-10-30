"""Text cases: empty and whitespace, sizes around a length limit, Unicode that changes length, order or
identity, control characters and text shaped like markup. Every character outside printable ASCII is
written here as an escape, so this file shows exactly what each case holds."""

from __future__ import annotations

from typing import Any

from .case import Case, Spec
from .rng import SplitMix64

KIND = "strings"
DEFAULTS = {"max_length": 64, "seeded": 3}
LIMITS = {"max_length": (1, 100000), "seeded": (0, 50)}

COMBINING = "\u0301\u0308\u0323\u0330\u0331\u0334\u0358\u0360"

S = Spec
SPECS = [
    S("strings.empty", "empty", "Nothing at all.", "Reject when required, with a message naming the field; never store it as a value."),
    S("strings.whitespace.space", "empty", "One space looks empty but is not.", "Treat as empty after trimming, or reject."),
    S("strings.whitespace.only", "empty", "Spaces only.", "Treat as empty after trimming, or reject."),
    S("strings.whitespace.no-break-space", "empty", "A no-break space survives most trim functions.", "Trim Unicode spaces too, or reject."),
    S("strings.whitespace.padded", "empty", "Leading and trailing spaces around a real value.", "Trim once, keep the inner text, and say so if the stored value differs."),
    S("strings.size.one-char", "size", "The shortest real value.", "Accept unless a minimum says otherwise."),
    S("strings.size.at-max", "size", "Exactly the length limit.", "Accept and store all of it."),
    S("strings.size.over-max", "size", "One past the length limit.", "Reject with the limit in the message; never cut it silently."),
    S("strings.size.huge", "size", "Sixty-four times the limit.", "Reject early, before it is parsed, logged or stored."),
    S("strings.size.long-word", "size", "A long word with no space to break at.", "Wrap or scroll inside its box; never overflow the page."),
    S("strings.size.long-token", "size", "A long address-like token with no spaces.", "Wrap or scroll inside its box; never overflow the page."),
    S("strings.unicode.combining-mark", "unicode", "A letter plus a separate accent mark (decomposed form).", "Compare and search after normalizing; never drop the mark."),
    S("strings.unicode.precomposed", "unicode", "The same name with a single accented letter (composed form).", "Equal to the decomposed form after normalizing."),
    S("strings.unicode.stacked-marks", "unicode", "One letter carrying eight combining marks.", "Count it as one character on screen and keep the marks inside the line box."),
    S("strings.unicode.rtl-arabic", "unicode", "Arabic, written right to left.", "Shown right to left, aligned to the start of its box."),
    S("strings.unicode.rtl-hebrew", "unicode", "Hebrew, written right to left.", "Shown right to left, aligned to the start of its box."),
    S("strings.unicode.rtl-with-digits", "unicode", "Right-to-left text mixed with digits and Latin letters.", "Digits and Latin runs keep their order inside the right-to-left text."),
    S("strings.unicode.bidi-override", "unicode", "A right-to-left override that makes text display in a different order than stored.", "Reject or strip direction controls in names and identifiers, or show them escaped."),
    S("strings.unicode.emoji", "unicode", "One emoji outside the Basic Multilingual Plane: two UTF-16 units, four UTF-8 bytes.", "Count it as one character; never split it in half."),
    S("strings.unicode.emoji-zwj-family", "unicode", "Several emoji joined by zero-width joiners into one picture.", "Count, cut and delete it as one character on screen."),
    S("strings.unicode.emoji-skin-tone", "unicode", "An emoji with a skin tone modifier.", "Keep the modifier attached; never separate the pair."),
    S("strings.unicode.flag", "unicode", "A flag made of two regional indicator letters.", "Keep the pair together; one half alone shows as a letter box."),
    S("strings.unicode.keycap", "unicode", "A digit, a variation selector and a combining keycap.", "Keep all three together."),
    S("strings.unicode.confusable", "unicode", "A Cyrillic letter that looks like a Latin one.", "Two names that look the same must not both pass as different accounts or labels."),
    S("strings.unicode.fullwidth", "unicode", "Full-width letters and digits.", "Normalize for comparison, or reject where only ASCII is allowed."),
    S("strings.unicode.ligature", "unicode", "A ligature character that compatibility normalization splits into two letters.", "Search and compare after compatibility normalization where the field is a name or keyword."),
    S("strings.unicode.sharp-s", "unicode", "Sharp s: upper case is two letters long.", "Case-insensitive compare uses case folding, not upper or lower case."),
    S("strings.unicode.dotted-capital-i", "unicode", "Capital I with dot: lower case adds a combining mark.", "Case-insensitive compare uses case folding and the length may change."),
    S("strings.unicode.non-bmp-ideograph", "unicode", "A CJK ideograph outside the Basic Multilingual Plane.", "Stored, counted and shown as one character."),
    S("strings.zero-width.space", "zero-width", "An invisible zero-width space inside a word.", "Visible in review, stripped or rejected in identifiers."),
    S("strings.zero-width.joiner", "zero-width", "An invisible zero-width joiner inside a word.", "Visible in review, stripped or rejected in identifiers."),
    S("strings.zero-width.non-joiner", "zero-width", "An invisible zero-width non-joiner inside a word.", "Kept in text where a language needs it; visible in review."),
    S("strings.zero-width.byte-order-mark", "zero-width", "A byte order mark at the start of a value.", "Strip it at input; two values that differ only by it are equal."),
    S("strings.zero-width.word-joiner", "zero-width", "An invisible word joiner inside a word.", "Visible in review, stripped or rejected in identifiers."),
    S("strings.control.newline", "control", "A line break inside a one-line field.", "Reject in one-line fields, or keep it and show it as a break; never split a record on it."),
    S("strings.control.crlf", "control", "A carriage return and line feed inside a value.", "Never let it start a new header, log line or CSV row."),
    S("strings.control.tab", "control", "A tab inside a value.", "Never let it shift a column in exports."),
    S("strings.control.nul", "control", "A NUL character, which ends strings in C and some databases.", "Reject, or store and return it unchanged; never truncate at it."),
    S("strings.control.line-separator", "control", "The Unicode line separator, which ends lines in some JavaScript and JSON tools.", "Escape it in scripts and JSON; never break a line on it silently."),
    S("strings.markup.angle-brackets", "markup", "Text with angle brackets and an ampersand.", "Shown as text, escaped exactly once, never interpreted as markup."),
    S("strings.markup.quotes", "markup", "Single and double quotes in a name.", "Stored and shown unchanged; never closes a quoted string."),
    S("strings.markup.template-braces", "markup", "Placeholders that template engines would fill.", "Shown literally; never filled from other data."),
    S("strings.markup.spreadsheet-formula", "markup", "A value a spreadsheet would run as a formula.", "Exports quote or prefix it so a spreadsheet shows it as text."),
    S("strings.markup.path-like", "markup", "A value that looks like a path that climbs out of a folder.", "Never used as a path without resolving and confining it."),
    S("strings.seeded.mixed", "seeded", "Seeded random text mixing letters, digits, marks, right-to-left letters, emoji and invisible characters.", "Round-trips unchanged; the same seed gives the same text."),
]
BY_LABEL = {spec.label: spec for spec in SPECS}

POOL = [
    "a", "b", "Z", "0", "7", " ", "-", "\u00e9", "\u00df", COMBINING[0], COMBINING[1], "\u05d0", "\u05e9", "\u0627", "\u0645",
    "\U0001f600", "\U0001f44d\U0001f3fd", "\u200b", "\u200d", "\u2060", "\u4e2d", "\uff21",
]


def cases(limits: dict[str, Any], rng: SplitMix64) -> list[Case]:
    n = limits["max_length"]
    fixed: list[tuple[str, Any]] = [
        ("strings.empty", ""),
        ("strings.whitespace.space", " "),
        ("strings.whitespace.only", "   "),
        ("strings.whitespace.no-break-space", "\u00a0"),
        ("strings.whitespace.padded", "  Test Volunteer  "),
        ("strings.size.one-char", "a"),
        ("strings.size.at-max", "a" * n),
        ("strings.size.over-max", "a" * (n + 1)),
        ("strings.size.huge", "a" * (n * 64)),
        ("strings.size.long-word", "Pneumonoultramicroscopicsilicovolcanoconiosis"),
        ("strings.size.long-token", "volunteer-" + "shift" * 12 + "-reminder-preferences"),
        ("strings.unicode.combining-mark", "Jose\u0301"),
        ("strings.unicode.precomposed", "Jos\u00e9"),
        ("strings.unicode.stacked-marks", "a" + COMBINING),
        ("strings.unicode.rtl-arabic", "\u0645\u0631\u062d\u0628\u0627"),
        ("strings.unicode.rtl-hebrew", "\u05e9\u05dc\u05d5\u05dd"),
        ("strings.unicode.rtl-with-digits", "\u05e9\u05dc\u05d5\u05dd 2026 ABC"),
        ("strings.unicode.bidi-override", "abc\u202edcba"),
        ("strings.unicode.emoji", "\U0001f600"),
        ("strings.unicode.emoji-zwj-family", "\U0001f468\u200d\U0001f469\u200d\U0001f467"),
        ("strings.unicode.emoji-skin-tone", "\U0001f44d\U0001f3fd"),
        ("strings.unicode.flag", "\U0001f1ef\U0001f1f5"),
        ("strings.unicode.keycap", "1\ufe0f\u20e3"),
        ("strings.unicode.confusable", "\u0430dmin"),
        ("strings.unicode.fullwidth", "\uff21\uff22\uff23\uff11\uff12\uff13"),
        ("strings.unicode.ligature", "\ufb01le"),
        ("strings.unicode.sharp-s", "stra\u00dfe"),
        ("strings.unicode.dotted-capital-i", "\u0130stanbul"),
        ("strings.unicode.non-bmp-ideograph", "\U00020bb7"),
        ("strings.zero-width.space", "ab\u200bcd"),
        ("strings.zero-width.joiner", "ab\u200dcd"),
        ("strings.zero-width.non-joiner", "ab\u200ccd"),
        ("strings.zero-width.byte-order-mark", "\ufeffname"),
        ("strings.zero-width.word-joiner", "ab\u2060cd"),
        ("strings.control.newline", "line one\nline two"),
        ("strings.control.crlf", "line one\r\nline two"),
        ("strings.control.tab", "a\tb"),
        ("strings.control.nul", "a\u0000b"),
        ("strings.control.line-separator", "a\u2028b"),
        ("strings.markup.angle-brackets", "<b>5 > 3 & 2 < 4</b>"),
        ("strings.markup.quotes", "O'Neil \"Jr\""),
        ("strings.markup.template-braces", "{{name}} ${name} %s {0}"),
        ("strings.markup.spreadsheet-formula", "=1+1"),
        ("strings.markup.path-like", "../../notes.txt"),
    ]
    out = [Case(KIND, BY_LABEL[label], value) for label, value in fixed]
    for _ in range(limits["seeded"]):
        length = rng.between(1, max(1, min(n, 24)))
        text = "".join(rng.choice(POOL) for _ in range(length))
        out.append(Case(KIND, BY_LABEL["strings.seeded.mixed"], text))
    return out
