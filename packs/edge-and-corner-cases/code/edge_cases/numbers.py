"""Number cases, written as the text a person, a form or a request body would send: the limits of a
field and one step past them, integer and floating-point edges, words a parser may accept as numbers,
and the many ways people write the same amount."""

from __future__ import annotations

from typing import Any

from .case import Case, Spec
from .rng import SplitMix64

KIND = "numbers"
DEFAULTS = {"minimum": 0, "maximum": 100, "seeded": 3}
LIMITS = {"minimum": (-(10**12), 10**12), "maximum": (-(10**12), 10**12), "seeded": (0, 50)}

S = Spec
SPECS = [
    S("numbers.boundary.minimum", "boundary", "The smallest allowed value.", "Accept."),
    S("numbers.boundary.below-minimum", "boundary", "One below the smallest allowed value.", "Reject with the limit in the message."),
    S("numbers.boundary.maximum", "boundary", "The largest allowed value.", "Accept."),
    S("numbers.boundary.above-maximum", "boundary", "One above the largest allowed value.", "Reject with the limit in the message."),
    S("numbers.boundary.zero", "boundary", "Zero.", "Accept or reject by the field's rule; never treat it as missing."),
    S("numbers.sign.negative-one", "sign", "Minus one, a common sentinel.", "Reject where counts cannot be negative; never read it as no limit."),
    S("numbers.sign.negative-zero", "sign", "Minus zero.", "Equal to zero, shown as 0."),
    S("numbers.sign.leading-plus", "sign", "A leading plus sign.", "Accept as the same number, or reject with a message."),
    S("numbers.integer.max-safe", "integer", "2**53 - 1, the largest safe integer: it and the integer after it are both exact in an IEEE-754 double.", "Round-trips exactly."),
    S("numbers.integer.max-safe-plus-one", "integer", "2**53, still exact, but the next integer is not, so a double cannot tell 2**53 from 2**53 + 1.", "Round-trips exactly or is rejected; never silently changed."),
    S("numbers.integer.max-safe-plus-two", "integer", "2**53 + 1, which a double rounds to 2**53.", "Kept exactly, as a string or a big integer, or rejected; never changed by one."),
    S("numbers.integer.int32-max", "integer", "The largest signed 32-bit integer.", "Accept where the field allows it."),
    S("numbers.integer.int32-overflow", "integer", "One past the largest signed 32-bit integer.", "Reject or store in a wider type; never wrap to a negative number."),
    S("numbers.integer.int64-max", "integer", "The largest signed 64-bit integer.", "Accept where the field allows it."),
    S("numbers.integer.int64-overflow", "integer", "One past the largest signed 64-bit integer.", "Reject; never wrap or saturate silently."),
    S("numbers.float.one-tenth", "float", "0.1, which binary floating point cannot hold exactly.", "Money and counts use decimal or integer units, never binary floats."),
    S("numbers.float.smallest-subnormal", "float", "The smallest positive double.", "Not read as zero where zero means something else."),
    S("numbers.float.largest", "float", "The largest finite double.", "Accept or reject by range; never overflow to infinity."),
    S("numbers.float.overflow", "float", "A literal too large for a double.", "Reject; many parsers turn it into infinity."),
    S("numbers.float.many-digits", "float", "More digits than a double keeps.", "Round once, by a stated rule, or reject."),
    S("numbers.word.nan", "word", "The word NaN, which some parsers accept as a number.", "Reject; it is not equal to itself and breaks sorting and totals."),
    S("numbers.word.infinity", "word", "The word Infinity.", "Reject."),
    S("numbers.word.negative-infinity", "word", "The word -Infinity.", "Reject."),
    S("numbers.format.thousands-comma", "format", "A thousands comma and a decimal point.", "Parse with the person's locale and show the value back, or reject."),
    S("numbers.format.decimal-comma", "format", "A thousands point and a decimal comma, the reverse of the case above.", "Parse with the person's locale and show the value back, or reject."),
    S("numbers.format.narrow-space-group", "format", "Groups separated by a narrow no-break space, with a decimal comma.", "Parse with the person's locale and show the value back, or reject."),
    S("numbers.format.apostrophe-group", "format", "Groups separated by an apostrophe.", "Parse with the person's locale and show the value back, or reject."),
    S("numbers.format.lakh-grouping", "format", "Indian grouping: one lakh.", "Parse with the person's locale and show the value back, or reject."),
    S("numbers.format.scientific", "format", "Scientific notation.", "Accept or reject on purpose; never read it as 1."),
    S("numbers.format.leading-zeros", "format", "Leading zeros, which some parsers read as octal.", "Read as decimal or reject; never as octal."),
    S("numbers.format.hex", "format", "A hexadecimal literal.", "Reject unless the field is hexadecimal."),
    S("numbers.format.surrounding-spaces", "format", "Spaces around the digits.", "Trim and accept, or reject; never fail later."),
    S("numbers.format.currency", "format", "A currency symbol before the amount.", "Reject or strip by a stated rule; never parse as zero."),
    S("numbers.format.percent", "format", "A percent sign after the number.", "Reject or convert by a stated rule; 50 percent is never 50."),
    S("numbers.format.fraction", "format", "A fraction.", "Reject unless fractions are allowed."),
    S("numbers.format.arabic-indic-digits", "format", "Arabic-Indic digits.", "Accept as the same digits or reject with a message; never as zero."),
    S("numbers.format.fullwidth-digits", "format", "Full-width digits.", "Accept as the same digits or reject with a message."),
    S("numbers.format.unicode-minus", "format", "A minus sign (U+2212) instead of a hyphen-minus.", "Accept as negative or reject; never as positive."),
    S("numbers.format.trailing-point", "format", "A decimal point with nothing after it.", "Accept as the integer or reject."),
    S("numbers.format.leading-point", "format", "A decimal point with nothing before it.", "Accept as the fraction or reject."),
    S("numbers.seeded.near-boundary", "seeded", "A seeded integer within two of the field's limits.", "Accepted inside the limits and rejected outside them."),
]
BY_LABEL = {spec.label: spec for spec in SPECS}


def cases(limits: dict[str, Any], rng: SplitMix64) -> list[Case]:
    low, high = limits["minimum"], limits["maximum"]
    if low > high:
        raise ValueError("numbers: minimum is above maximum")
    bounds = {"minimum": low, "maximum": high}
    fixed: list[tuple[str, str, dict[str, Any]]] = [
        ("numbers.boundary.minimum", str(low), bounds),
        ("numbers.boundary.below-minimum", str(low - 1), bounds),
        ("numbers.boundary.maximum", str(high), bounds),
        ("numbers.boundary.above-maximum", str(high + 1), bounds),
        ("numbers.boundary.zero", "0", bounds),
        ("numbers.sign.negative-one", "-1", {}),
        ("numbers.sign.negative-zero", "-0", {}),
        ("numbers.sign.leading-plus", "+5", {}),
        ("numbers.integer.max-safe", str(2**53 - 1), {}),
        ("numbers.integer.max-safe-plus-one", str(2**53), {}),
        ("numbers.integer.max-safe-plus-two", str(2**53 + 1), {}),
        ("numbers.integer.int32-max", str(2**31 - 1), {}),
        ("numbers.integer.int32-overflow", str(2**31), {}),
        ("numbers.integer.int64-max", str(2**63 - 1), {}),
        ("numbers.integer.int64-overflow", str(2**63), {}),
        ("numbers.float.one-tenth", "0.1", {}),
        ("numbers.float.smallest-subnormal", "5e-324", {}),
        ("numbers.float.largest", "1.7976931348623157e308", {}),
        ("numbers.float.overflow", "1e309", {}),
        ("numbers.float.many-digits", "3.14159265358979323846264338327950288", {}),
        ("numbers.word.nan", "NaN", {}),
        ("numbers.word.infinity", "Infinity", {}),
        ("numbers.word.negative-infinity", "-Infinity", {}),
        ("numbers.format.thousands-comma", "1,000.50", {"locale_hint": "en-US"}),
        ("numbers.format.decimal-comma", "1.000,50", {"locale_hint": "de-DE"}),
        ("numbers.format.narrow-space-group", "1\u202f000,50", {"locale_hint": "fr-FR"}),
        ("numbers.format.apostrophe-group", "1'000.50", {"locale_hint": "de-CH"}),
        ("numbers.format.lakh-grouping", "1,00,000", {"locale_hint": "en-IN"}),
        ("numbers.format.scientific", "1e3", {}),
        ("numbers.format.leading-zeros", "007", {}),
        ("numbers.format.hex", "0x1A", {}),
        ("numbers.format.surrounding-spaces", " 42 ", {}),
        ("numbers.format.currency", "$5.00", {}),
        ("numbers.format.percent", "50%", {}),
        ("numbers.format.fraction", "1/2", {}),
        ("numbers.format.arabic-indic-digits", "\u0661\u0662\u0663", {}),
        ("numbers.format.fullwidth-digits", "\uff11\uff12\uff13", {}),
        ("numbers.format.unicode-minus", "\u22125", {}),
        ("numbers.format.trailing-point", "5.", {}),
        ("numbers.format.leading-point", ".5", {}),
    ]
    out = [Case(KIND, BY_LABEL[label], value, context) for label, value, context in fixed]
    for _ in range(limits["seeded"]):
        edge = rng.choice((low, high))
        out.append(Case(KIND, BY_LABEL["numbers.seeded.near-boundary"], str(edge + rng.between(-2, 2)), bounds))
    return out
