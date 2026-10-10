"""Whether Loop 2 target storage can be used on this host.

Two levels: the ``loop2_targets_enabled`` setting (off by default -> DISABLED) and a cached
probe of the required target tables (missing -> UNAVAILABLE). A transient probe error is raised,
never cached, so one network blip cannot switch the feature off for the cache period.
Reads use the state to return an empty result; writes refuse before any side effect.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from enum import StrEnum


class TargetAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"


class TargetCapability:
    def __init__(
        self,
        enabled: bool,
        probe: Callable[[], Awaitable[bool]],
        *,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enabled = enabled
        self._probe = probe
        self._ttl = ttl_seconds
        self._clock = clock
        self._cached: tuple[float, TargetAvailability] | None = None

    async def state(self) -> TargetAvailability:
        if not self._enabled:
            return TargetAvailability.DISABLED
        now = self._clock()
        if self._cached is not None and now - self._cached[0] < self._ttl:
            return self._cached[1]
        provisioned = await self._probe()  # TargetsUnavailable propagates uncached
        state = TargetAvailability.AVAILABLE if provisioned else TargetAvailability.UNAVAILABLE
        self._cached = (now, state)
        return state
