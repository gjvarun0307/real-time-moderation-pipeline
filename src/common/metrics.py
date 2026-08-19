"""Every metric the whole pipeline exposes, registered in one place.
"""

from prometheus_client import Counter, Gauge

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

ingest_lang_disagreement_total = Counter(
    "ingest_lang_disagreement_total",
    "Declared language tag disagrees with fastText's prediction",
    ["declared", "predicted"],
)

ingest_duplicates_total = Counter(
    "ingest_duplicates_total",
    "Events dropped as duplicates of a recently seen post",
)

ingest_sample_rate = Gauge(
    "ingest_sample_rate",
    "Current adaptive-sampling admission rate",
)

ingest_queue_depth = Gauge(
    "ingest_queue_depth",
    "Current bounded-queue depth",
)
