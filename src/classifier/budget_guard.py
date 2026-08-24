"""Budget-guarded escalation sampling: deterministic bps roll capped by a
real daily quota tracked in Redis.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as redis
import structlog

from common.determinism import deterministic_fraction
from common.metrics import adjudicator_budget_exhausted_total
from common.redis_flag import RedisFlag

logger = structlog.get_logger()

_KEY_TTL_SECONDS = 172_800  # 2 days — generous margin past UTC midnight


class BudgetCounter:
    """Redis-backed daily escalation counter, keyed by UTC date so it ages
    out naturally."""

    def __init__(self, redis_url: str, key_prefix: str) -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix

    def _key(self, now: datetime) -> str:
        return f"{self._key_prefix}:{now:%Y-%m-%d}"

    async def current_count(self, now: datetime) -> int:
        value = await self._client.get(self._key(now))
        return int(value) if value is not None else 0

    async def increment(self, now: datetime) -> int:
        key = self._key(now)
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, _KEY_TTL_SECONDS)
        return int(count)

    async def close(self) -> None:
        await self._client.aclose()


@dataclass(frozen=True)
class BudgetDecision:
    escalate: bool
    budget_exhausted: bool
    overflow_active: bool = False


class BudgetGuard:
    """Decides whether an uncertain-band post gets real LLM adjudication,
    deterministic on post ID and capped by a Redis daily counter."""

    def __init__(
        self, counter: BudgetCounter, sample_bps: int, daily_cap: int, overflow_flag: RedisFlag
    ) -> None:
        self._counter = counter
        self._sample_bps = sample_bps
        self._daily_cap = daily_cap
        self._overflow_flag = overflow_flag

    async def decide(self, post_id: str, now: datetime | None = None) -> BudgetDecision:
        now = now or datetime.now(UTC)

        if await self._overflow_flag.is_active():
            return BudgetDecision(escalate=False, budget_exhausted=False, overflow_active=True)

        if await self._counter.current_count(now) >= self._daily_cap:
            adjudicator_budget_exhausted_total.inc()
            logger.warning("adjudicator_budget_exhausted", cap=self._daily_cap)
            return BudgetDecision(escalate=False, budget_exhausted=True)

        if deterministic_fraction(post_id) * 10_000 >= self._sample_bps:
            return BudgetDecision(escalate=False, budget_exhausted=False)

        await self._counter.increment(now)
        return BudgetDecision(escalate=True, budget_exhausted=False)

    async def close(self) -> None:
        await self._counter.close()
        await self._overflow_flag.close()
