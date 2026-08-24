from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestSettings(BaseSettings):
    """Env-configured settings for ingest-service."""

    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env")

    # Jetstream connection. 
    jetstream_endpoints: list[str] = [
        "wss://jetstream2.us-east.bsky.network/subscribe",
        "wss://jetstream1.us-east.bsky.network/subscribe",
        "wss://jetstream1.us-west.bsky.network/subscribe",
        "wss://jetstream2.us-west.bsky.network/subscribe",
    ]
    wanted_collections: str = "app.bsky.feed.post"

    # Cursor persistence. Redis service name matches
    # infra/k8s/base/redis/service.yaml.
    redis_url: str = "redis://redis:6379/0"
    cursor_redis_key: str = "ingest:cursor"
    cursor_persist_interval_seconds: float = 5.0
    # flagged as assumption, until verified.
    cursor_max_staleness_seconds: int = 3600

    # Reconnect backoff :base 1s, cap 60s, full jitter.
    reconnect_base_delay_seconds: float = 1.0
    reconnect_max_delay_seconds: float = 60.0

    # Sized for replay load, not live traffic — a 20k queue at the live
    # ~40/sec rate is 500s of buffer and will never fill.
    queue_max: int = 20_000

    # Redpanda. Service name matches infra/k8s/base/redpanda/service.yaml.
    kafka_bootstrap_servers: str = "redpanda:9092"
    posts_raw_topic: str = "posts.raw"
    dlq_topic: str = "moderation.dlq"

    # No default on purpose — must come from env, never hardcoded.
    author_hash_salt: str

    fasttext_model_path: str | None = None


class ClassifierSettings(BaseSettings):
    """Env-configured settings for classifier-service."""

    model_config = SettingsConfigDict(env_prefix="CLASSIFIER_", env_file=".env")

    # Redpanda. Service name matches infra/k8s/base/redpanda/service.yaml.
    kafka_bootstrap_servers: str = "redpanda:9092"
    posts_raw_topic: str = "posts.raw"
    verdicts_topic: str = "moderation.verdicts"
    escalate_topic: str = "moderation.escalate"
    consumer_group: str = "classifier"

    # No default on purpose — must come from env, never hardcoded.
    database_url: str

    # Deterministic on post ID (src.common.determinism), same idea as
    # the budget guard's escalation sampling — reproducible under replay.
    allow_sample_bps: int = 100  # 1% of ALLOW

    # Tier 0 lexicons.
    lexicon_dir: str = "models/lexicons"

    # Tier 1 — model artifact fetched from R2 at startup, not baked into
    # the image, so a new export rolls via config + restart.
    tier1_version_tag: str = "v1-70dee6e"
    tier1_model_cache_dir: str = "/app/models/tier1"
    max_seq_len: int = 192  # ja p99, docs/MEASURED_BASELINE.md
    onnx_intra_op_threads: int = 2  # ~1.5x throughput vs 1 thread, metrics.local.md

    # Routing thresholds. Global defaults; lang_threshold_overrides lets a
    # specific lang_predicted override any of tau_lo/tau_hi/tau_mid once
    # per-language eval data exists.
    tau_lo: float = 0.15
    tau_hi: float = 0.85
    tau_mid: float = 0.5  # midpoint placeholder — spec doesn't pin this value
    lang_threshold_overrides: dict[str, dict[str, float]] = {}

    # Budget guard. Redis service name matches infra/k8s/base/redis/service.yaml.
    redis_url: str = "redis://redis:6379/0"
    budget_key_prefix: str = "classifier:budget"
    adjudication_sample_bps: int = 87  # docs/BUDGET.md — Groq quota, 20% margin
    adjudication_daily_cap: int = 800  # same quota basis, hard backstop

    # R2 (Cloudflare) — bucket/account/access-key-id are non-secret, see
    # classifier.tier1.download. Only the secret key comes from env.
    # No default on purpose — must come from env, never hardcoded.
    r2_secret_access_key: str

