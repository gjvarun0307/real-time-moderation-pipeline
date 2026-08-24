"""A simple async token bucket for shaping per-provider request rate.
"""

import asyncio
import time
from collections.abc import Callable


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float) -> None:
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._tokens = capacity
        self._last_refill: float | None = None

    def _refill(self, now: float) -> None:
        if self._last_refill is None:
            self._last_refill = now
            return
        elapsed = max(0.0, now - self._last_refill)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_second)
        self._last_refill = now

    async def acquire(
        self, cost: float = 1.0, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        """Debits cost tokens, sleeping first if not enough are available yet."""
        now = clock()
        self._refill(now)

        if self._tokens >= cost:
            self._tokens -= cost
            return

        shortfall = cost - self._tokens
        wait_seconds = shortfall / self._refill_per_second
        await asyncio.sleep(wait_seconds)
        # We waited exactly long enough for `shortfall` tokens to refill,
        # ending at `cost` tokens before debiting — don't re-query the
        # clock for the token count, only for the refill timestamp.
        self._tokens = 0.0
        self._last_refill = clock()
