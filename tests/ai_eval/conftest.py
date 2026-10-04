"""Safety rails for the AI evaluation suite.

* Deterministic tests may not open non-loopback sockets (asyncio on Windows needs loopback).
* Live tests (tests/ai_eval/live/) are exempt, but are skipped unless explicitly enabled.
"""
from __future__ import annotations

import socket
from pathlib import Path

import pytest

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_LIVE_DIR = Path(__file__).parent / "live"


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    if _LIVE_DIR in Path(str(request.node.fspath)).parents:
        yield
        return
    real = socket.socket.connect

    def guarded(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _LOOPBACK:
            raise AssertionError(f"ai_eval deterministic tests must not use the network (connect to {host!r})")
        return real(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield
