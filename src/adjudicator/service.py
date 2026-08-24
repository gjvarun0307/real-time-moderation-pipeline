import asyncio
from pathlib import Path

import aiohttp
import orjson
import structlog

from adjudicator.circuit_breaker import CircuitBreaker
from adjudicator.client import AdjudicatorClient
from adjudicator.consumer import EscalateConsumer
from adjudicator.overflow import should_activate_overflow
from adjudicator.producer import AdjudicatorProducer
from adjudicator.prompt import PromptBuilder
from adjudicator.providers.base import AdjudicationProvider
from adjudicator.providers.gemini import GeminiProvider
from adjudicator.providers.groq import GroqProvider
from adjudicator.token_bucket import TokenBucket
from adjudicator.verdict_builder import build_verdict
from common.config import AdjudicatorSettings
from common.metrics import (
    adjudicator_consumer_lag,
    adjudicator_dlq_total,
    adjudicator_overflow_active,
)
from common.redis_flag import RedisFlag
from common.schemas import EscalateMessage

logger = structlog.get_logger()

LAG_REPORT_INTERVAL_SECONDS = 10.0


class AdjudicatorService:
    def __init__(
        self,
        settings: AdjudicatorSettings,
        consumer: EscalateConsumer,
        producer: AdjudicatorProducer,
        overflow_flag: RedisFlag,
        client: AdjudicatorClient | None = None,
    ) -> None:
        self._settings = settings
        self._consumer = consumer
        self._producer = producer
        self._overflow_flag = overflow_flag
        # Pre-supplied in tests; built for real in start() otherwise —
        # aiohttp.ClientSession needs a running event loop at construction
        # time, same constraint as the aiokafka clients.
        self._client = client
        self._prompt_builder = PromptBuilder(Path(settings.prompt_path))
        self._session: aiohttp.ClientSession | None = None
        self._ready = False

    async def start(self) -> None:
        await self._consumer.start()
        await self._producer.start()

        if self._client is None:
            self._session = aiohttp.ClientSession()
            providers: list[AdjudicationProvider] = [
                GroqProvider(
                    self._session,
                    self._settings.groq_api_key,
                    self._settings.groq_model,
                    self._settings.groq_base_url,
                ),
                GeminiProvider(
                    self._session,
                    self._settings.gemini_api_key,
                    self._settings.gemini_model,
                    self._settings.gemini_base_url,
                ),
            ]
            breakers = {
                p.name: CircuitBreaker(
                    self._settings.circuit_failure_threshold, self._settings.circuit_open_seconds
                )
                for p in providers
            }
            groq_capacity = self._settings.groq_rpm * 0.8
            gemini_capacity = self._settings.gemini_rpm * 0.8
            buckets = {
                "groq": TokenBucket(groq_capacity, groq_capacity / 60),
                "gemini": TokenBucket(gemini_capacity, gemini_capacity / 60),
            }
            self._client = AdjudicatorClient(
                providers=providers,
                breakers=breakers,
                buckets=buckets,
                prompt_builder=self._prompt_builder,
                settings=self._settings,
            )

        self._ready = True

    async def stop(self) -> None:
        self._ready = False
        await self._consumer.stop()
        await self._producer.stop()
        if self._session is not None:
            await self._session.close()
        await self._overflow_flag.close()

    def is_ready(self) -> bool:
        return self._ready

    async def run_consume_loop(self) -> None:
        async for record in self._consumer.messages():
            try:
                await self._handle_record(record.value)
            except Exception:
                logger.exception("adjudicator_record_handling_failed")
                continue
            await self._consumer.commit()

    async def run_lag_reporter_loop(self) -> None:
        while True:
            await asyncio.sleep(LAG_REPORT_INTERVAL_SECONDS)
            lag = await self._consumer.current_lag()
            adjudicator_consumer_lag.set(lag)
            if should_activate_overflow(lag, self._settings.overflow_lag_threshold):
                await self._overflow_flag.set_active()
                adjudicator_overflow_active.set(1)
            else:
                await self._overflow_flag.clear()
                adjudicator_overflow_active.set(0)

    async def _handle_record(self, raw_value: bytes) -> None:
        assert self._client is not None
        message = EscalateMessage.model_validate(orjson.loads(raw_value))
        outcome = await self._client.adjudicate(message)

        if outcome.kind == "dlq":
            reason = outcome.reason or "unknown"
            await self._producer.produce_dlq(
                reason,
                {"escalate_message": message.model_dump(), **(outcome.context or {})},
            )
            adjudicator_dlq_total.labels(reason=reason).inc()
            return

        assert outcome.response is not None
        assert outcome.provider is not None
        verdict = build_verdict(
            message,
            outcome.response,
            provider=outcome.provider,
            prompt_version=self._prompt_builder.version,
        )
        await self._producer.produce_verdict(verdict)


def build_service(settings: AdjudicatorSettings) -> AdjudicatorService:
    return AdjudicatorService(
        settings=settings,
        consumer=EscalateConsumer(
            settings.kafka_bootstrap_servers,
            settings.escalate_topic,
            settings.consumer_group,
            settings.max_poll_records,
        ),
        producer=AdjudicatorProducer(
            settings.kafka_bootstrap_servers, settings.verdicts_topic, settings.dlq_topic
        ),
        overflow_flag=RedisFlag(
            settings.redis_url, settings.overflow_flag_key, settings.overflow_flag_ttl_seconds
        ),
    )
