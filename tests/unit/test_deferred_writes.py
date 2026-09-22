import asyncio
from uuid import uuid4

from app import deferred_writes
from app.deferred_writes import DeferredWrites


def run(coro):
    return asyncio.run(coro)


def test_jobs_for_a_session_run_in_order() -> None:
    order: list[int] = []

    async def go():
        writes, sid = DeferredWrites(), uuid4()
        for n, delay in ((1, 0.05), (2, 0.0), (3, 0.01)):
            async def job(n=n, delay=delay):
                await asyncio.sleep(delay)
                order.append(n)
            writes.enqueue(sid, f"k{n}", job)
        await writes.flush(sid)

    run(go())
    assert order == [1, 2, 3]


def test_same_key_is_queued_once() -> None:
    count: list[int] = []

    async def go():
        writes, sid = DeferredWrites(), uuid4()
        async def job():
            count.append(1)
        for _ in range(3):
            writes.enqueue(sid, "turn:complete", job)
        await writes.flush(sid)

    run(go())
    assert count == [1]


def test_failed_write_is_retried_then_lands(monkeypatch) -> None:
    monkeypatch.setattr(deferred_writes, "RETRY_DELAYS", (0.0, 0.0, 0.0))
    attempts: list[int] = []

    async def go():
        writes, sid = DeferredWrites(), uuid4()
        async def job():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("temporary")
        writes.enqueue(sid, "k", job)
        await writes.flush(sid)

    run(go())
    assert len(attempts) == 3


def test_permanent_failure_does_not_block_later_writes(monkeypatch) -> None:
    monkeypatch.setattr(deferred_writes, "RETRY_DELAYS", (0.0,))
    done: list[str] = []

    async def go():
        writes, sid = DeferredWrites(), uuid4()
        async def bad():
            raise RuntimeError("down")
        async def good():
            done.append("ok")
        writes.enqueue(sid, "bad", bad)
        writes.enqueue(sid, "good", good)
        await writes.flush(sid)

    run(go())
    assert done == ["ok"]


def test_sessions_do_not_wait_on_each_other() -> None:
    finished: list[str] = []

    async def go():
        writes, a, b = DeferredWrites(), uuid4(), uuid4()
        async def slow():
            await asyncio.sleep(0.1)
            finished.append("a")
        async def fast():
            finished.append("b")
        writes.enqueue(a, "slow", slow)
        writes.enqueue(b, "fast", fast)
        await writes.flush_all()

    run(go())
    assert finished == ["b", "a"]
