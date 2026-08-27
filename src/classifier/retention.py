"""Daily retention cleanup for verdicts/verdict_rollups — run as a k8s
CronJob (infra/k8s/base/classifier/retention-cronjob.yaml), not inside
classifier-service's live consume loop.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg
import structlog

from common.config import RetentionSettings

logger = structlog.get_logger()

_DELETE_OLD_SAMPLES = """
DELETE FROM verdicts
WHERE persist_reason = 'sample' AND decided_time < $1
"""

_DELETE_OLD_REPLAY = """
DELETE FROM verdicts
WHERE source = 'replay' AND decided_time < $1
"""

_DELETE_OLD_ROLLUPS = """
DELETE FROM verdict_rollups WHERE bucket_minute < $1
"""


async def run_retention(settings: RetentionSettings) -> dict[str, str]:
    """Runs the daily retention cleanup, returning each statement's asyncpg
    status string (e.g. "DELETE 42")."""
    now = datetime.now(UTC)
    conn = await asyncpg.connect(settings.database_url)
    try:
        return {
            "old_samples_deleted": await conn.execute(
                _DELETE_OLD_SAMPLES, now - timedelta(days=settings.sample_retention_days)
            ),
            "old_replay_deleted": await conn.execute(
                _DELETE_OLD_REPLAY, now - timedelta(days=settings.replay_retention_days)
            ),
            "old_rollups_deleted": await conn.execute(
                _DELETE_OLD_ROLLUPS, now - timedelta(days=settings.rollup_retention_days)
            ),
        }
    finally:
        await conn.close()


async def main() -> None:
    # required fields with no default (database_url) come from env at
    # runtime; mypy can't see that, hence the ignore here specifically
    settings = RetentionSettings()  # type: ignore[call-arg]
    results = await run_retention(settings)
    logger.info("retention_job_completed", **results)


if __name__ == "__main__":
    asyncio.run(main())
