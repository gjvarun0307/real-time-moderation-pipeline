"""Daily retention cleanup for verdicts/verdict_rollups — run as a k8s
CronJob (infra/k8s/base/classifier/retention-cronjob.yaml), not inside
classifier-service's live consume loop.
"""

import asyncio

import asyncpg
import structlog

from common.config import RetentionSettings

logger = structlog.get_logger()

_DELETE_OLD_SAMPLES = """
DELETE FROM verdicts
WHERE persist_reason = 'sample' AND decided_time < now() - $1::interval
"""

_DELETE_OLD_REPLAY = """
DELETE FROM verdicts
WHERE source = 'replay' AND decided_time < now() - $1::interval
"""

_DELETE_OLD_ROLLUPS = """
DELETE FROM verdict_rollups WHERE bucket_minute < now() - $1::interval
"""


async def run_retention(settings: RetentionSettings) -> dict[str, str]:
    """Runs the daily retention cleanup, returning each statement's asyncpg
    status string (e.g. "DELETE 42")."""
    conn = await asyncpg.connect(settings.database_url)
    try:
        return {
            "old_samples_deleted": await conn.execute(
                _DELETE_OLD_SAMPLES, f"{settings.sample_retention_days} days"
            ),
            "old_replay_deleted": await conn.execute(
                _DELETE_OLD_REPLAY, f"{settings.replay_retention_days} days"
            ),
            "old_rollups_deleted": await conn.execute(
                _DELETE_OLD_ROLLUPS, f"{settings.rollup_retention_days} days"
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
