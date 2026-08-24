"""A shared, TTL-based boolean flag in Redis — one service sets it,
another reads it. Used for the classifier<->adjudicator overflow signal.
"""

import redis.asyncio as redis


class RedisFlag:
    """TTL-based flag: `set_active()` refreshes the TTL so a crashed writer
    auto-clears the flag within one TTL window instead of jamming the
    reader open or closed forever."""

    def __init__(self, redis_url: str, key: str, ttl_seconds: float) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key = key
        self._ttl_seconds = ttl_seconds

    async def set_active(self) -> None:
        await self._client.set(self._key, "1", ex=int(self._ttl_seconds))

    async def clear(self) -> None:
        await self._client.delete(self._key)

    async def is_active(self) -> bool:
        return await self._client.exists(self._key) > 0

    async def close(self) -> None:
        await self._client.aclose()
