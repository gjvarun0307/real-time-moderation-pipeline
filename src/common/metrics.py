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

classifier_tier0_resolved_total = Counter(
    "classifier_tier0_resolved_total",
    "Tier 0 resolutions, by decision and dominant script",
    ["decision", "script"],
)

classifier_tier1_inference_seconds = Histogram(
    "classifier_tier1_inference_seconds",
    "Tier 1 ONNX single-item inference wall time",
)

classifier_tier1_batch_size = Histogram(
    "classifier_tier1_batch_size",
    "Items per Tier 1 inference call",
    buckets=(1, 2, 4, 8, 16, 32),
)

classifier_tier1_seq_len = Histogram(
    "classifier_tier1_seq_len",
    "Tokenized sequence length actually fed to Tier 1",
    buckets=(16, 32, 64, 96, 128, 160, 192),
)

classifier_escalated_total = Counter(
    "classifier_escalated_total",
    "Posts actually produced to moderation.escalate, by language",
    ["lang"],
)

classifier_escalation_sampled_out_total = Counter(
    "classifier_escalation_sampled_out_total",
    "Uncertain-band posts resolved locally instead of escalated, by language",
    ["lang"],
)

classifier_score = Histogram(
    "classifier_score",
    "Calibrated Tier 1 toxic probability",
    buckets=(0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.0),
)

adjudicator_budget_exhausted_total = Counter(
    "adjudicator_budget_exhausted_total",
    "Times the daily escalation budget was already spent when the guard was consulted",
)
