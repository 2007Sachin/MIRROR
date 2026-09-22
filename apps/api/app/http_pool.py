"""Shared keep-alive HTTP connections for Supabase calls.

The repositories used to open a new client (and a new TLS connection) for every
call, which measured about 527 ms per call against about 281 ms on a reused
connection. When VOICE_HTTP_POOL is on, `pooled()` hands out one shared client per
event loop instead. When it is off, `pooled()` behaves exactly like the old code.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .config import get_settings

_clients: dict[int, httpx.AsyncClient] = {}


def _shared() -> httpx.AsyncClient:
    loop_id = id(asyncio.get_running_loop())
    client = _clients.get(loop_id)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=20.0),
            transport=httpx.AsyncHTTPTransport(retries=1),
            timeout=20,
        )
        _clients[loop_id] = client
    return client


class _Pooled:
    """Forwards requests to the shared client with the caller's timeout."""

    def __init__(self, client: httpx.AsyncClient, timeout: float) -> None:
        self._client = client
        self._timeout = timeout

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        kwargs.setdefault("timeout", self._timeout)
        try:
            return await self._client.request(method, url, **kwargs)
        except (httpx.RemoteProtocolError, httpx.ReadError) as exc:
            # A kept-alive connection the server already closed. Reads are safe to repeat.
            if method.upper() != "GET":
                raise exc
            return await self._client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)


class _PooledContext:
    def __init__(self, timeout: float) -> None:
        self._timeout = timeout

    async def __aenter__(self) -> _Pooled:
        return _Pooled(_shared(), self._timeout)

    async def __aexit__(self, *_exc: object) -> None:
        return None


def pooled(timeout: float = 10):
    """Drop-in for `httpx.AsyncClient(timeout=...)` inside `async with`."""
    if get_settings().voice_http_pool:
        return _PooledContext(timeout)
    return httpx.AsyncClient(timeout=timeout)
