import time

from rbloom import Bloom

from common.metrics import ingest_duplicates_total

DEFAULT_CAPACITY = 200_000
DEFAULT_FALSE_POSITIVE_RATE = 0.001
DEFAULT_WINDOW_SECONDS = 3600.0


def build_post_key(did: str, collection: str, rkey: str) -> str:
    return f"at://{did}/{collection}/{rkey}"


class BloomDedup:
    """Sliding-window duplicate detector backed by two rotating bloom
    filters, so membership checks always cover the trailing window
    without ever rebuilding a filter mid-window.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        false_positive_rate: float = DEFAULT_FALSE_POSITIVE_RATE,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._capacity = capacity
        self._false_positive_rate = false_positive_rate
        self._window_seconds = window_seconds
        self._current = Bloom(capacity, false_positive_rate)
        self._previous = Bloom(capacity, false_positive_rate)
        self._window_started_at = time.monotonic()

    def _rotate_if_due(self) -> None:
        if time.monotonic() - self._window_started_at >= self._window_seconds:
            self._previous = self._current
            self._current = Bloom(self._capacity, self._false_positive_rate)
            self._window_started_at = time.monotonic()

    def is_duplicate(self, key: str) -> bool:
        """Checks `key` against the current and previous window, marking
        it seen if it's new. Returns whether it was already present.
        """
        self._rotate_if_due()
        if key in self._current or key in self._previous:
            ingest_duplicates_total.inc()
            return True
        self._current.add(key)
        return False
