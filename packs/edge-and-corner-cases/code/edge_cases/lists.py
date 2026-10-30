"""List cases: sizes around a page, duplicates that differ only in case, spacing or normalization,
orders that break stable or naive sorting, and items a list rarely expects."""

from __future__ import annotations

from typing import Any

from .case import Case, Spec
from .rng import SplitMix64

KIND = "lists"
DEFAULTS = {"page_size": 10, "seeded": 2}
LIMITS = {"page_size": (1, 10000), "seeded": (0, 50)}

S = Spec
SPECS = [
    S("lists.size.empty", "size", "No items.", "An empty state that says so, never an error or a blank screen."),
    S("lists.size.one", "size", "One item.", "Singular wording and layout where they differ."),
    S("lists.size.two", "size", "Two items.", "Plural wording; separators between items."),
    S("lists.size.page", "size", "Exactly one page of items.", "No empty second page and no next-page control."),
    S("lists.size.page-plus-one", "size", "One more than a page.", "A second page with one item, reachable and labelled."),
    S("lists.size.huge", "size", "A hundred pages of items.", "Paged or streamed, with a bounded response; never loaded whole into one screen."),
    S("lists.duplicates.exact", "duplicates", "The same value twice.", "Folded together or rejected by a stated rule; never counted twice by mistake."),
    S("lists.duplicates.case", "duplicates", "Values that differ only in letter case.", "Treated as the same or different on purpose, by the field's rule."),
    S("lists.duplicates.spacing", "duplicates", "Values that differ only in surrounding spaces.", "Trimmed before comparison."),
    S("lists.duplicates.normalization", "duplicates", "Values that differ only in Unicode normalization.", "Equal after normalizing."),
    S("lists.duplicates.same-id", "duplicates", "Two records with the same id and different fields.", "Rejected, or the conflict reported; never one silently wins."),
    S("lists.order.sorted", "order", "Already in order.", "Kept in order."),
    S("lists.order.reversed", "order", "In reverse order.", "Sorted correctly."),
    S("lists.order.equal-keys", "order", "Records with equal sort keys.", "Equal keys keep their original order (a stable sort), or the tie-break is stated."),
    S("lists.order.numeric-strings", "order", "Numbers written as text.", "Sorted as numbers where they are numbers: 9 before 10."),
    S("lists.order.case-and-accents", "order", "Words with capitals and accents.", "Sorted by the reader's language rules, not by code point."),
    S("lists.items.null", "items", "A null item in the middle.", "Rejected, or skipped with a count; never shown as the word null."),
    S("lists.items.empty-string", "items", "An empty string item.", "Rejected, or shown as empty on purpose."),
    S("lists.items.mixed-types", "items", "The same value as text, number and boolean.", "Rejected, or each kept as its own type."),
    S("lists.items.nested-empty", "items", "Empty lists inside a list.", "Handled without recursion errors."),
    S("lists.seeded.shuffled-with-duplicates", "seeded", "A seeded shuffle of a page of items with some repeated.", "The same items and counts come back, in the stated order."),
]
BY_LABEL = {spec.label: spec for spec in SPECS}


def items(n: int) -> list[str]:
    return [f"item-{i:0{max(2, len(str(n)))}d}" for i in range(1, n + 1)]


def cases(limits: dict[str, Any], rng: SplitMix64) -> list[Case]:
    page = limits["page_size"]
    fixed: list[tuple[str, Any, dict[str, Any]]] = [
        ("lists.size.empty", [], {}),
        ("lists.size.one", ["a"], {}),
        ("lists.size.two", ["a", "b"], {}),
        ("lists.size.page", items(page), {"page_size": page}),
        ("lists.size.page-plus-one", items(page + 1), {"page_size": page}),
        ("lists.size.huge", items(page * 100), {"page_size": page}),
        ("lists.duplicates.exact", ["a", "b", "a"], {}),
        ("lists.duplicates.case", ["Ann", "ann", "ANN"], {}),
        ("lists.duplicates.spacing", ["Ann", " Ann", "Ann "], {}),
        ("lists.duplicates.normalization", ["Jos\u00e9", "Jose\u0301"], {}),
        ("lists.duplicates.same-id", [{"id": "s-1", "name": "Ann"}, {"id": "s-1", "name": "Bo"}], {}),
        ("lists.order.sorted", ["a", "b", "c"], {}),
        ("lists.order.reversed", ["c", "b", "a"], {}),
        ("lists.order.equal-keys", [{"key": 1, "id": "first"}, {"key": 1, "id": "second"}, {"key": 0, "id": "third"}], {"sort_by": "key"}),
        ("lists.order.numeric-strings", ["10", "9", "100"], {}),
        ("lists.order.case-and-accents", ["apple", "Banana", "\u00e9clair", "Zebra"], {}),
        ("lists.items.null", ["a", None, "b"], {}),
        ("lists.items.empty-string", ["a", "", "b"], {}),
        ("lists.items.mixed-types", ["1", 1, True], {}),
        ("lists.items.nested-empty", [[], [[]]], {}),
    ]
    out = [Case(KIND, BY_LABEL[label], value, context) for label, value, context in fixed]
    for _ in range(limits["seeded"]):
        base = items(page)
        repeats = [rng.choice(base) for _ in range(rng.between(1, max(1, page // 3)))]
        out.append(Case(KIND, BY_LABEL["lists.seeded.shuffled-with-duplicates"], rng.shuffled(base + repeats), {"page_size": page}))
    return out
