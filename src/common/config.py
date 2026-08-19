from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestSettings(BaseSettings):
    """Env-configured settings for ingest-service. Spec §4.1, §15."""

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
