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
    consumer_group: str = "classifier"

    # No default on purpose — must come from env, never hardcoded.
    database_url: str

    # Deterministic on post ID (src.common.determinism), same idea as
    # the budget guard's escalation sampling — reproducible under replay.
    allow_sample_bps: int = 100  # 1% of ALLOW

