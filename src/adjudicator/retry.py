"""Retry helper implementing spec §4.3's exact rule: max 2 retries,
full-jitter exponential backoff, never retry a client error.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable

from adjudicator.providers.base import ProviderClientError, ProviderRateLimited, ProviderServerError


async def call_with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    base_delay: float,
    max_delay: float,
) -> T:
    attempt = 0
    while True:
        try:
            return await fn()
        except ProviderClientError:
            raise
        except (ProviderServerError, ProviderRateLimited):
            if attempt >= max_retries:
                raise
            delay = random.uniform(0, min(max_delay, base_delay * 2**attempt))
            await asyncio.sleep(delay)
            attempt += 1
