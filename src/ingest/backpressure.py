import asyncio

import structlog

from common.determinism import deterministic_fraction
from common.metrics import ingest_dropped_total, ingest_queue_depth, ingest_sample_rate

logger = structlog.get_logger()


def sample_tier(utilization: float) -> tuple[str, float]:
    if utilization < 0.70:
        return "NORMAL", 1.00
    if utilization < 0.85:
        return "DEGRADED", 0.50
    if utilization < 0.95:
        return "HEAVY", 0.20
    return "CRITICAL", 0.05


class AdaptiveQueue[T]:
    """Bounded queue with deterministic sampling that admits fewer items
    as it fills, rather than blocking or growing unbounded.
    """

    def __init__(self, maxsize: int) -> None:
        self.queue: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._maxsize = maxsize
        self._current_tier = "NORMAL"

    def offer(self, key: str, item: T) -> bool:
        """Admits or drops `item`, keyed deterministically on `key` so
        the same key always gets the same decision at a given
        utilization tier. Returns whether it was admitted.
        """
        utilization = self.queue.qsize() / self._maxsize
        tier, rate = sample_tier(utilization)
        ingest_sample_rate.set(rate)

        if tier != self._current_tier:
            logger.warning(
                "ingest_sample_tier_transition",
                from_tier=self._current_tier,
                to_tier=tier,
                utilization=round(utilization, 3),
                sample_rate=rate,
            )
            self._current_tier = tier

        if deterministic_fraction(key) >= rate:
            ingest_dropped_total.labels(reason=f"sample_{tier.lower()}").inc()
            return False

        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:
            ingest_dropped_total.labels(reason="queue_full").inc()
            return False

        ingest_queue_depth.set(self.queue.qsize())
        return True
