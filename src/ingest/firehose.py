import asyncio
import random
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import orjson
import structlog
import websockets
from websockets.exceptions import WebSocketException

from common.config import IngestSettings
from common.metrics import ingest_reconnects_total
from common.schemas import RawEvent
from ingest.cursor_store import CursorStore, clamp_cursor

logger = structlog.get_logger()


class FirehoseSource(ABC):
    """keep this interface stable so an endpoint change 
    (e.g. Jetstream v2,) costs one adapter.
    """

    @abstractmethod
    def stream(self) -> AsyncIterator[RawEvent]: ...


def compute_backoff(attempt: int, base: float, cap: float) -> float:
    """Full-jitter exponential backoff. Spec §4.1 step 2: base 1s, cap 60s."""
    return random.uniform(0, min(cap, base * (2**attempt)))


class JetstreamSource(FirehoseSource):
    """WS client for Bluesky Jetstream.
    """

    def __init__(self, settings: IngestSettings, cursor_store: CursorStore) -> None:
        self._settings = settings
        self._cursor_store = cursor_store
        self._last_cursor_us: int | None = None

    async def _effective_start_cursor(self) -> int | None:
        persisted = await self._cursor_store.load()
        now_us = int(time.time() * 1_000_000)
        return clamp_cursor(persisted, now_us, self._settings.cursor_max_staleness_seconds)

    def _build_url(self, endpoint: str, cursor_us: int | None) -> str:
        url = f"{endpoint}?wantedCollections={self._settings.wanted_collections}"
        if cursor_us is not None:
            url += f"&cursor={cursor_us}"
        return url

    async def stream(self) -> AsyncIterator[RawEvent]:
        endpoints = self._settings.jetstream_endpoints
        endpoint_idx = 0
        attempt = 0

        while True:
            endpoint = endpoints[endpoint_idx % len(endpoints)]
            cursor_us = await self._effective_start_cursor()
            url = self._build_url(endpoint, cursor_us)

            try:
                async with websockets.connect(url) as ws:
                    logger.info("jetstream_connected", endpoint=endpoint, cursor_us=cursor_us)
                    attempt = 0  # reset backoff on a successful connect
                    last_persist = time.monotonic()

                    async for raw_frame in ws:
                        event = RawEvent.model_validate(orjson.loads(raw_frame))
                        self._last_cursor_us = event.time_us

                        now_mono = time.monotonic()
                        persist_interval = self._settings.cursor_persist_interval_seconds
                        if now_mono - last_persist >= persist_interval:
                            await self._cursor_store.persist(self._last_cursor_us)
                            last_persist = now_mono

                        yield event

            except (OSError, WebSocketException) as exc:
                ingest_reconnects_total.labels(endpoint=endpoint).inc()
                delay = compute_backoff(
                    attempt,
                    self._settings.reconnect_base_delay_seconds,
                    self._settings.reconnect_max_delay_seconds,
                )
                logger.warning(
                    "jetstream_disconnected",
                    endpoint=endpoint,
                    error=str(exc),
                    attempt=attempt,
                    retry_in_seconds=round(delay, 2),
                )
                attempt += 1
                endpoint_idx += 1
                if self._last_cursor_us is not None:
                    await self._cursor_store.persist(self._last_cursor_us)
                await asyncio.sleep(delay)
