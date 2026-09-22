from __future__ import annotations

import asyncio
from uuid import uuid4

from app.deferred_writes import get_deferred_writes
from app.session_liveness import SessionLiveness, sweep_idle_sessions
from tests.test_interview_engine import USER_A, active_session, make_engine


class Ticker:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_fresh_other_lease_conflicts_and_same_lease_refreshes() -> None:
    tick = Ticker()
    live = SessionLiveness(tick)
    sid = uuid4()
    assert live.heartbeat(sid, USER_A, "lease-aaaaaaaa", 30)
    assert live.heartbeat(sid, USER_A, "lease-aaaaaaaa", 30)
    tick.t += 20
    assert not live.heartbeat(sid, USER_A, "lease-bbbbbbbb", 30)
    tick.t += 31
    assert live.heartbeat(sid, USER_A, "lease-bbbbbbbb", 30)  # stale lease is taken over


def test_idle_session_is_paused_and_unknown_sessions_skipped() -> None:
    async def run() -> None:
        engine, _, clock = make_engine()
        session = await active_session(engine)
        tick = Ticker()
        live = SessionLiveness(tick)
        live.heartbeat(session.id, USER_A, "lease-aaaaaaaa", 30)
        assert await sweep_idle_sessions(live, engine, get_deferred_writes(), 90) == 0
        tick.t += 100
        clock.advance(100)
        assert await sweep_idle_sessions(live, engine, get_deferred_writes(), 90) == 1
        assert engine.is_paused(await engine._require(session.id, USER_A))
        assert live.idle(0) == []
        # never-registered sessions are never touched
        other = await active_session(engine)
        assert await sweep_idle_sessions(live, engine, get_deferred_writes(), 0) == 0
        assert not engine.is_paused(await engine._require(other.id, USER_A))

    asyncio.run(run())
