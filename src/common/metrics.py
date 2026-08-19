"""Every metric the whole pipeline exposes, registered in one place.
"""

from prometheus_client import Counter

ingest_reconnects_total = Counter(
    "ingest_reconnects_total",
    "Jetstream WebSocket reconnect attempts",
    ["endpoint"],
)
