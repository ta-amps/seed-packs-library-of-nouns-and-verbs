"""Health probes."""

READY = False


def mark_ready():
    global READY
    READY = True


def healthz():
    return {"status": "ok"}


def livez():
    return {"ok": READY}


def readyz(store):
    store.ping()
    return {"ok": True}
