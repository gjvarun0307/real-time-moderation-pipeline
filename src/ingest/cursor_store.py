import redis.asyncio as redis


def clamp_cursor(
    persisted_cursor_us: int | None, now_us: int, max_staleness_seconds: int
) -> int | None:
    """Bound how far back a resumed cursor can replay from."""
    if persisted_cursor_us is None:
        return None
    floor_us = now_us - max_staleness_seconds * 1_000_000
    return max(persisted_cursor_us, floor_us)


class CursorStore:
    """Redis-backed cursor persistence."""

    def __init__(self, redis_url: str, key: str) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key = key

    async def load(self) -> int | None:
        value = await self._client.get(self._key)
        return int(value) if value is not None else None

    async def persist(self, cursor_us: int) -> None:
        await self._client.set(self._key, cursor_us)

    async def close(self) -> None:
        await self._client.aclose()
