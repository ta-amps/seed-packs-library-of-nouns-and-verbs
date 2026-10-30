"""Booking rules."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._types import SlotRow


def book_slot(store, when) -> "SlotRow":
    return store.save({"when": when})
