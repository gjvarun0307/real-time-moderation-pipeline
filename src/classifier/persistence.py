from datetime import UTC, datetime

import asyncpg

from common.determinism import deterministic_fraction
from common.schemas import Verdict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
    id              UUID PRIMARY KEY,
    post_uri        TEXT NOT NULL,
    author_hash     CHAR(32) NOT NULL,
    lang_predicted  VARCHAR(8) NOT NULL,
    lang_declared   VARCHAR(8),
    lang_confidence REAL,
    decision        VARCHAR(16) NOT NULL,
    resolved_tier   SMALLINT NOT NULL,
    score_toxic     REAL,
    score_severe    REAL,
    score_obscene   REAL,
    score_threat    REAL,
    score_insult    REAL,
    score_identity  REAL,
    low_confidence  BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_sampled_out BOOLEAN NOT NULL DEFAULT FALSE,
    persist_reason  VARCHAR(24) NOT NULL,
    model_version   VARCHAR(64) NOT NULL,
    prompt_version  VARCHAR(32),
    adjudicator_provider VARCHAR(32),
    source          VARCHAR(8) NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    decided_time    TIMESTAMPTZ NOT NULL,
    latency_ms      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS verdicts_decided_time_idx ON verdicts (decided_time DESC);
CREATE INDEX IF NOT EXISTS verdicts_lang_decided_idx
    ON verdicts (lang_predicted, decided_time DESC);
CREATE INDEX IF NOT EXISTS verdicts_tier_decided_idx ON verdicts (resolved_tier, decided_time DESC);

CREATE TABLE IF NOT EXISTS verdict_rollups (
    bucket_minute   TIMESTAMPTZ NOT NULL,
    lang            VARCHAR(8)  NOT NULL,
    decision        VARCHAR(16) NOT NULL,
    resolved_tier   SMALLINT    NOT NULL,
    source          VARCHAR(8)  NOT NULL,
    n               INTEGER     NOT NULL,
    sum_latency_ms  BIGINT      NOT NULL,
    sum_score_toxic REAL        NOT NULL,
    PRIMARY KEY (bucket_minute, lang, decision, resolved_tier, source)
);
CREATE INDEX IF NOT EXISTS verdict_rollups_bucket_idx ON verdict_rollups (bucket_minute DESC);
"""

_INSERT_VERDICT = """
INSERT INTO verdicts (
    id, post_uri, author_hash, lang_predicted, lang_declared, lang_confidence,
    decision, resolved_tier, score_toxic, score_severe, score_obscene,
    score_threat, score_insult, score_identity, low_confidence,
    escalation_sampled_out, persist_reason, model_version, prompt_version,
    adjudicator_provider, source, event_time, decided_time, latency_ms
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
    $17, $18, $19, $20, $21, $22, $23, $24
)
"""

_UPSERT_ROLLUP = """
INSERT INTO verdict_rollups (
    bucket_minute, lang, decision, resolved_tier, source, n, sum_latency_ms, sum_score_toxic
) VALUES ($1, $2, $3, $4, $5, 1, $6, $7)
ON CONFLICT (bucket_minute, lang, decision, resolved_tier, source) DO UPDATE SET
    n = verdict_rollups.n + 1,
    sum_latency_ms = verdict_rollups.sum_latency_ms + EXCLUDED.sum_latency_ms,
    sum_score_toxic = verdict_rollups.sum_score_toxic + EXCLUDED.sum_score_toxic
"""


def persist_reason(verdict: Verdict, allow_sample_bps: int) -> str | None:
    """Which full-row persistence reason applies, if any — spec §6's
    selective-persistence rule. `None` means the verdict only ever
    becomes a rollup increment, never a full row.
    """
    if verdict.decision in ("BLOCK", "REVIEW"):
        return "block"
    if verdict.resolved_tier == 2:
        return "tier2"
    if verdict.low_confidence:
        return "low_conf"
    if deterministic_fraction(verdict.post_uri) * 10_000 < allow_sample_bps:
        return "sample"
    return None


class VerdictStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def start(self) -> None:
        # asyncpg.create_pool is itself a coroutine — must be awaited from
        # inside an async context, so this can't happen in __init__.
        self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def insert_verdict(self, verdict: Verdict, reason: str) -> None:
        if self._pool is None:
            raise RuntimeError("VerdictStore.start() was never called")
        event_time = datetime.fromtimestamp(verdict.event_time_us / 1_000_000, tz=UTC)
        decided_time = datetime.fromtimestamp(verdict.decided_time_us / 1_000_000, tz=UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                _INSERT_VERDICT,
                verdict.id,
                verdict.post_uri,
                verdict.author_hash,
                verdict.lang_predicted,
                verdict.lang_declared,
                verdict.lang_confidence,
                verdict.decision,
                verdict.resolved_tier,
                verdict.score_toxic,
                verdict.score_severe,
                verdict.score_obscene,
                verdict.score_threat,
                verdict.score_insult,
                verdict.score_identity,
                verdict.low_confidence,
                verdict.escalation_sampled_out,
                reason,
                verdict.model_version,
                verdict.prompt_version,
                verdict.adjudicator_provider,
                verdict.source,
                event_time,
                decided_time,
                verdict.latency_ms,
            )

    async def upsert_rollup(self, verdict: Verdict) -> None:
        if self._pool is None:
            raise RuntimeError("VerdictStore.start() was never called")
        decided_time = datetime.fromtimestamp(verdict.decided_time_us / 1_000_000, tz=UTC)
        bucket_minute = decided_time.replace(second=0, microsecond=0)
        score_toxic = verdict.score_toxic or 0.0
        async with self._pool.acquire() as conn:
            await conn.execute(
                _UPSERT_ROLLUP,
                bucket_minute,
                verdict.lang_predicted,
                verdict.decision,
                verdict.resolved_tier,
                verdict.source,
                verdict.latency_ms,
                score_toxic,
            )
