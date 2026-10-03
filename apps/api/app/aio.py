"""Run independent reads at once without changing which failure the caller sees."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any


async def gather_in_order(*awaitables: Awaitable[Any]) -> list[Any]:
    """Like awaiting each in turn, but concurrently: the first failure *in argument order*
    is raised, exactly as sequential awaits would have raised it."""
    results = await asyncio.gather(*awaitables, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return results


if __name__ == "__main__":
    async def _demo() -> None:
        async def slow_fail() -> None:
            await asyncio.sleep(0.02)
            raise KeyError("first")

        async def fast_fail() -> None:
            raise ValueError("second")

        assert await gather_in_order(asyncio.sleep(0, 1), asyncio.sleep(0, 2)) == [1, 2]
        try:
            await gather_in_order(slow_fail(), fast_fail())
        except KeyError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected the first failure in argument order")

    asyncio.run(_demo())
    print("ok")
