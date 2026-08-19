"""Every metric the whole pipeline exposes, registered in one place.
"""

from prometheus_client import Counter, Gauge, Histogram

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

classifier_verdicts_total = Counter(
    "classifier_verdicts_total",
    "Verdicts produced, by decision",
    ["decision"],
)

classifier_persisted_total = Counter(
    "classifier_persisted_total",
    "Verdicts written as a full Postgres row, by persist reason",
    ["persist_reason"],
)

classifier_rollup_writes_total = Counter(
    "classifier_rollup_writes_total",
    "Verdicts folded into a 1-minute rollup counter instead of a full row",
)

classifier_verdict_latency_seconds = Histogram(
    "classifier_verdict_latency_seconds",
    "Time from event_time to decided_time",
)

classifier_consumer_lag = Gauge(
    "classifier_consumer_lag",
    "Summed lag across assigned posts.raw partitions",
)
