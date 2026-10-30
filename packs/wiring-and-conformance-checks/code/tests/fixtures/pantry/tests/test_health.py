from unittest.mock import patch

from pantry_app import health


def test_healthz_says_ok():
    assert health.healthz() == {"status": "ok"}


@patch("pantry_app.health.READY", True)
def test_livez_when_ready():
    assert health.livez() == {"ok": True}
