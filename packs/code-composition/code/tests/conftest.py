"""Shared fixtures: a socket- and process-level guard for offline seed export and import tests."""

from __future__ import annotations

import os
import socket
import subprocess
from collections.abc import Callable
from typing import Any

import pytest


class OfflineViolation(AssertionError):
    """Raised when guarded code tries to reach the network or start a process."""


@pytest.fixture
def offline_guard(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Block outbound sockets, DNS, inet binds and process creation; record every attempt.

    Socket pairs used by an in-process event loop stay available. Tests assert the returned
    list is empty, so an attempt that code under test catches and hides is still detected.
    """
    attempts: list[str] = []

    def refuse(name: str) -> Callable[..., Any]:
        def blocked(*_args: Any, **_kwargs: Any) -> Any:
            attempts.append(name)
            raise OfflineViolation(f"{name} is blocked: seed export and import must stay offline")

        return blocked

    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        if hasattr(socket.socket, name):
            monkeypatch.setattr(socket.socket, name, refuse(f"socket.{name}"))
    original_bind = socket.socket.bind

    def bind(self: socket.socket, address: Any) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append("socket.bind")
            raise OfflineViolation(
                "socket.bind is blocked: seed export and import must stay offline"
            )
        original_bind(self, address)

    monkeypatch.setattr(socket.socket, "bind", bind)
    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        monkeypatch.setattr(socket, name, refuse(f"socket.{name}"))

    class RefusedPopen(subprocess.Popen[Any]):
        """Still a class, so `subprocess.Popen[bytes]` annotations keep importing."""

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self._child_created = False  # keeps Popen.__del__ a no-op
            attempts.append("subprocess.Popen")
            raise OfflineViolation(
                "subprocess.Popen is blocked: seed export and import must stay offline"
            )

    monkeypatch.setattr(subprocess, "Popen", RefusedPopen)
    for name in ("system", "posix_spawn", "posix_spawnp", "fork", "forkpty"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, refuse(f"os.{name}"))
    try:
        import _posixsubprocess
    except ImportError:  # pragma: no cover - non-POSIX platforms
        pass
    else:
        monkeypatch.setattr(_posixsubprocess, "fork_exec", refuse("_posixsubprocess.fork_exec"))
    return attempts
