"""Synthetic tests of the pantry app. The mock scan reads them; nothing runs them."""

import unittest
from unittest import mock

from pantry_app import routes, slots
from pantry_app.store import Store


class BookingTests(unittest.TestCase):
    @mock.patch("pantry_app.store.Store.save")
    def test_book_returns_a_slot(self, save):
        save.return_value = {"when": "2026-11-02T10:00"}
        self.assertEqual(routes.book("2026-11-02T10:00")["when"], "2026-11-02T10:00")

    def test_book_slot_saves_the_row(self):
        store = Store(":memory:")
        slots.book_slot(store, "2026-11-02T10:00")
        self.assertEqual(len(store.rows), 1)


class CancelTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(Store, "delete", return_value=1)
        self.delete = patcher.start()
        self.addCleanup(patcher.stop)

    def test_cancel_removes_the_slot(self):
        self.assertEqual(routes.cancel("2026-11-02T10:00"), 1)
