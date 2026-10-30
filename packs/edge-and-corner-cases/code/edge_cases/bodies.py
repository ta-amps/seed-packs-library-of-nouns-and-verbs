"""Request body cases for a JSON API, as the raw text a client sends, with the content type in the
context: broken syntax, input strict parsers reject and lenient ones accept, values a schema should
refuse, sizes past a limit and the wrong content type. A worker sends them only to a local build or a
test target a person named."""

from __future__ import annotations

from typing import Any

from .case import Case, Spec
from .rng import SplitMix64

KIND = "bodies"
DEFAULTS = {"max_bytes": 1024, "depth": 64, "seeded": 3}
LIMITS = {"max_bytes": (16, 10**8), "depth": (1, 100000), "seeded": (0, 50)}
JSON_TYPE = "application/json"
BASE = '{"name":"Test Volunteer","spots":2}'
MUTATIONS = ['"', "{", "}", "[", "]", ",", ":", "\\", "0", "-", "e", "n", " "]

S = Spec
SPECS = [
    S("bodies.valid.minimal", "valid", "A well-formed body, as a control.", "Accepted; every other body is compared with this one."),
    S("bodies.syntax.truncated", "syntax", "A body cut off before its end.", "400 with a message that says the JSON is incomplete; nothing stored."),
    S("bodies.syntax.trailing-comma", "syntax", "A trailing comma, which JSON does not allow.", "400; never parsed by a lenient fallback."),
    S("bodies.syntax.single-quotes", "syntax", "Single-quoted strings, which JSON does not allow.", "400."),
    S("bodies.syntax.comment", "syntax", "A comment, which JSON does not allow.", "400."),
    S("bodies.syntax.nan-token", "syntax", "A NaN token, which JSON does not allow and some parsers accept.", "400; never stored as a number."),
    S("bodies.syntax.byte-order-mark", "syntax", "A byte order mark before the JSON text.", "Rejected, or ignored on purpose; never a 500."),
    S("bodies.syntax.empty", "syntax", "An empty body.", "400 that says a body is required."),
    S("bodies.syntax.whitespace-only", "syntax", "A body of spaces.", "400 that says a body is required."),
    S("bodies.semantics.duplicate-keys", "semantics", "The same key twice; RFC 8259 leaves the result to each parser.", "Rejected; never one value silently wins."),
    S("bodies.semantics.big-integer", "semantics", "An integer a double cannot hold exactly.", "Rejected or kept exactly; never changed by one."),
    S("bodies.semantics.unknown-field", "semantics", "A field the schema does not define.", "Rejected or ignored by the API's stated rule, the same way every time."),
    S("bodies.semantics.null-required", "semantics", "A required field set to null.", "400 naming the field."),
    S("bodies.semantics.wrong-type", "semantics", "A text field sent as a number.", "400 naming the field and the expected type."),
    S("bodies.semantics.top-level-array", "semantics", "An array where an object is expected.", "400; never a 500."),
    S("bodies.semantics.top-level-null", "semantics", "The JSON literal null as the whole body.", "400; never a 500."),
    S("bodies.semantics.lone-surrogate-escape", "semantics", "An escape for half of a UTF-16 pair, valid JSON syntax that is not valid Unicode.", "Rejected; never stored as text that cannot be encoded."),
    S("bodies.encoding.escaped-unicode", "encoding", "A name written with a Unicode escape.", "Equal to the same name written directly."),
    S("bodies.size.deep-nesting", "size", "Arrays nested one level deeper than the nesting limit.", "Rejected by the depth limit; never a stack overflow."),
    S("bodies.size.over-limit", "size", "A body just over the size limit.", "413 before the body is parsed or stored."),
    S("bodies.header.text-plain", "header", "A JSON body labelled text/plain.", "415, or accepted by a stated rule; the same every time."),
    S("bodies.header.form-encoded", "header", "A JSON body labelled as a form.", "415 or 400 with a message."),
    S("bodies.header.missing", "header", "No content type at all.", "415 or a stated default; never a 500."),
    S("bodies.header.wrong-charset", "header", "A charset parameter on JSON, which RFC 8259 does not define and says has no effect on compliant recipients.", "Read as UTF-8 whatever the label says, or refused with a message; never decoded as Latin-1."),
    S("bodies.seeded.mutated", "seeded", "The control body with one seeded character inserted, deleted or replaced.", "Accepted only when still valid JSON for the schema; otherwise 400, never a 500."),
]
BY_LABEL = {spec.label: spec for spec in SPECS}


def mutate(text: str, rng: SplitMix64) -> tuple[str, dict[str, Any]]:
    at = rng.below(len(text))
    action = rng.choice(("insert", "delete", "replace"))
    char = rng.choice(MUTATIONS)
    if action == "insert":
        return text[:at] + char + text[at:], {"mutation": "insert", "at": at, "char": char}
    if action == "delete":
        return text[:at] + text[at + 1:], {"mutation": "delete", "at": at}
    return text[:at] + char + text[at + 1:], {"mutation": "replace", "at": at, "char": char}


def cases(limits: dict[str, Any], rng: SplitMix64) -> list[Case]:
    depth, max_bytes = limits["depth"], limits["max_bytes"]
    json_type = {"content_type": JSON_TYPE}
    filler = "a" * max(0, max_bytes - len('{"name":""}') + 1)
    fixed: list[tuple[str, str, dict[str, Any]]] = [
        ("bodies.valid.minimal", BASE, json_type),
        ("bodies.syntax.truncated", BASE[:-1], json_type),
        ("bodies.syntax.trailing-comma", '{"name":"Test Volunteer","spots":2,}', json_type),
        ("bodies.syntax.single-quotes", "{'name':'Test Volunteer','spots':2}", json_type),
        ("bodies.syntax.comment", '{"name":"Test Volunteer" /* note */,"spots":2}', json_type),
        ("bodies.syntax.nan-token", '{"name":"Test Volunteer","spots":NaN}', json_type),
        ("bodies.syntax.byte-order-mark", "\ufeff" + BASE, json_type),
        ("bodies.syntax.empty", "", json_type),
        ("bodies.syntax.whitespace-only", "   ", json_type),
        ("bodies.semantics.duplicate-keys", '{"name":"Test Volunteer","name":"Other Volunteer","spots":2}', json_type),
        ("bodies.semantics.big-integer", '{"name":"Test Volunteer","spots":9007199254740993}', json_type),
        ("bodies.semantics.unknown-field", '{"name":"Test Volunteer","spots":2,"nickname":"TV"}', json_type),
        ("bodies.semantics.null-required", '{"name":null,"spots":2}', json_type),
        ("bodies.semantics.wrong-type", '{"name":42,"spots":2}', json_type),
        ("bodies.semantics.top-level-array", "[" + BASE + "]", json_type),
        ("bodies.semantics.top-level-null", "null", json_type),
        ("bodies.semantics.lone-surrogate-escape", '{"name":"\\ud800","spots":2}', json_type),
        ("bodies.encoding.escaped-unicode", '{"name":"Jos\\u00e9","spots":2}', json_type),
        ("bodies.size.deep-nesting", "[" * (depth + 1) + "]" * (depth + 1), {**json_type, "max_depth": depth}),
        ("bodies.size.over-limit", '{"name":"' + filler + '"}', {**json_type, "max_bytes": max_bytes}),
        ("bodies.header.text-plain", BASE, {"content_type": "text/plain"}),
        ("bodies.header.form-encoded", BASE, {"content_type": "application/x-www-form-urlencoded"}),
        ("bodies.header.missing", BASE, {"content_type": None}),
        ("bodies.header.wrong-charset", BASE, {"content_type": "application/json; charset=iso-8859-1"}),
    ]
    out = [Case(KIND, BY_LABEL[label], value, context) for label, value, context in fixed]
    for _ in range(limits["seeded"]):
        text, how = mutate(BASE, rng)
        out.append(Case(KIND, BY_LABEL["bodies.seeded.mutated"], text, {**json_type, **how}))
    return out
