"""Routes for booking and cancelling pickup slots."""

import importlib

from . import slots
from .health import healthz, livez, readyz
from .store import Store

STORE = Store("pantry.db")
SMS = importlib.import_module("pantry_app.plugins.sms")
ROUTES = {}


def route(path):
    def register(func):
        ROUTES[path] = func
        return func
    return register


@route("/book")
def book(when):
    slot = slots.book_slot(STORE, when)
    SMS.send_confirmation(slot)
    return slot


@route("/cancel")
def cancel(when):
    return STORE.delete(when)


@route("/healthcheck")
def service_check():
    return {"up": True}


def bookings():
    return STORE.rows


def serve(config):
    return {"routes": sorted(ROUTES), "probes": [healthz, livez, readyz], "slot_minutes": config.slot_minutes,
            "opens_at": config.open_hour}
