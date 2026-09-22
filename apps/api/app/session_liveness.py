"""In-memory liveness registry: one live tab per conversation, and auto-pause when it goes quiet.

IMPORTANT: the registry lives in this process only. It is lost on every API restart
(and is not shared between workers). That is safe by design: an unknown session is never
auto-paused, and the next heartbeat from an open room simply re-registers it.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

logger = logging.getLogger("mirror.liveness")

OPEN_ELSEWHERE = {
    "code": "SESSION_OPEN_ELSEWHERE",
    "message": "This conversation is open in another tab. You can continue there, or close it and continue here.",
}


@dataclass
class _Entry:
    lease_id: str
    user_id: UUID
    last_seen: float


class SessionLiveness:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[UUID, _Entry] = {}

    def heartbeat(self, session_id: UUID, user_id: UUID, lease_id: str, lease_seconds: float) -> bool:
        """Refresh the lease. Returns False when a different lease is still fresh."""
        now = self._clock()
        current = self._entries.get(session_id)
        if current and current.lease_id != lease_id and now - current.last_seen < lease_seconds:
            return False
        self._entries[session_id] = _Entry(lease_id, user_id, now)
        return True

    def release(self, session_id: UUID) -> None:
        self._entries.pop(session_id, None)

    def idle(self, idle_seconds: float) -> list[tuple[UUID, UUID]]:
        now = self._clock()
        return [(sid, e.user_id) for sid, e in list(self._entries.items()) if now - e.last_seen >= idle_seconds]


_liveness = SessionLiveness()


def get_liveness() -> SessionLiveness:
    return _liveness


async def sweep_idle_sessions(liveness: SessionLiveness, engine, deferred_writes, idle_seconds: float) -> int:
    """Pause every registered session that has gone quiet. Never raises."""
    paused = 0
    for session_id, user_id in liveness.idle(idle_seconds):
        try:
            await deferred_writes.flush(session_id)
            await engine.pause(session_id, user_id)
            paused += 1
        except Exception:  # not active, completed, gone, or a transient failure
            logger.info("idle pause skipped for %s", session_id, exc_info=True)
        liveness.release(session_id)  # a returning room re-registers on its next heartbeat
    return paused


async def run_idle_pause_loop(get_engine, get_writes, idle_seconds: float, interval: float = 15.0) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            await sweep_idle_sessions(_liveness, get_engine(), get_writes(), idle_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("idle pause sweep failed")
