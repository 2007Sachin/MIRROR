"""Ordered, retried background writes for the voice turn (flag: VOICE_ASYNC_PERSIST).

Transcript rows (the candidate turn and the interviewer turn) stay synchronous, so the next
turn always reads complete history. Only non-critical writes are deferred here: analytics
events, latency metrics and the idempotency bookkeeping row.

Guarantees
  - Per-session ordering: jobs for one session run one at a time, in the order queued.
  - Idempotency: a job key (turn id + name) is queued at most once.
  - Retries: three attempts with backoff; a final failure is logged with its key.
  - Flush: pause, close, end and shutdown call `flush(session_id)` before they continue.
  - If queueing fails for any reason the job runs inline, so nothing is silently dropped.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from uuid import UUID

logger = logging.getLogger("mirror.deferred_writes")

Job = Callable[[], Awaitable[object]]
RETRY_DELAYS = (0.5, 1.0, 2.0)
REMEMBERED_KEYS = 512


class DeferredWrites:
    def __init__(self) -> None:
        self._tails: dict[UUID, asyncio.Task[None]] = {}
        self._seen: dict[UUID, deque[str]] = {}

    def enqueue(self, session_id: UUID, key: str, job: Job) -> None:
        seen = self._seen.setdefault(session_id, deque(maxlen=REMEMBERED_KEYS))
        if key in seen:
            return
        seen.append(key)
        previous = self._tails.get(session_id)
        self._tails[session_id] = asyncio.ensure_future(self._run(previous, key, job))

    async def _run(self, previous: asyncio.Task[None] | None, key: str, job: Job) -> None:
        if previous is not None:
            await asyncio.shield(previous)
        for attempt, delay in enumerate((*RETRY_DELAYS, None)):
            try:
                await job()
                return
            except Exception:  # noqa: BLE001 - a deferred write must never crash the worker
                if delay is None:
                    logger.exception("deferred write failed permanently", extra={"key": key})
                    return
                logger.warning("deferred write retry", extra={"key": key, "attempt": attempt + 1})
                await asyncio.sleep(delay)

    async def flush(self, session_id: UUID) -> None:
        """Wait until every write queued so far for this session has finished."""
        tail = self._tails.get(session_id)
        if tail is not None:
            await asyncio.shield(tail)
            if self._tails.get(session_id) is tail:
                self._tails.pop(session_id, None)

    async def flush_all(self) -> None:
        for session_id in list(self._tails):
            await self.flush(session_id)


_writer = DeferredWrites()


def get_deferred_writes() -> DeferredWrites:
    return _writer
