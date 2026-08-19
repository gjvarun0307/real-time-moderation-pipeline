"""Every metric the whole pipeline exposes, registered in one place.
"""

from prometheus_client import Counter

ingest_reconnects_total = Counter(
    "ingest_reconnects_total",
    "Jetstream WebSocket reconnect attempts",
    ["endpoint"],
)

ingest_events_received_total = Counter(
    "ingest_events_received_total",
    "Raw Jetstream frames received, before any filtering",
)

ingest_dropped_total = Counter(
    "ingest_dropped_total",
    "Events excluded before reaching the bounded queue",
    ["reason"],
)
