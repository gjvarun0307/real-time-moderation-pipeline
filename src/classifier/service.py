import asyncio

import orjson
import structlog

from classifier.consumer import PostsConsumer
from classifier.decision import decide_stub
from classifier.persistence import VerdictStore, persist_reason
from classifier.producer import VerdictProducer
from common.config import ClassifierSettings
from common.metrics import (
    classifier_consumer_lag,
    classifier_persisted_total,
    classifier_rollup_writes_total,
    classifier_verdict_latency_seconds,
    classifier_verdicts_total,
)
from common.schemas import PostsRawMessage

logger = structlog.get_logger()

LAG_REPORT_INTERVAL_SECONDS = 10.0


class ClassifierService:
    def __init__(
        self,
        settings: ClassifierSettings,
        consumer: PostsConsumer,
        producer: VerdictProducer,
        store: VerdictStore,
    ) -> None:
        self._settings = settings
        self._consumer = consumer
        self._producer = producer
        self._store = store
        self._ready = False

    async def start(self) -> None:
        await self._consumer.start()
        await self._producer.start()
        await self._store.start()
        self._ready = True

    async def stop(self) -> None:
        self._ready = False
        await self._consumer.stop()
        await self._producer.stop()
        await self._store.stop()

    def is_ready(self) -> bool:
        return self._ready

    async def run_consume_loop(self) -> None:
        async for record in self._consumer.messages():
            try:
                await self._handle_record(record.value)
            except Exception:
                logger.exception("classifier_record_handling_failed")
                continue
            await self._consumer.commit()

    async def run_lag_reporter_loop(self) -> None:
        while True:
            await asyncio.sleep(LAG_REPORT_INTERVAL_SECONDS)
            classifier_consumer_lag.set(await self._consumer.current_lag())

    async def _handle_record(self, raw_value: bytes) -> None:
        message = PostsRawMessage.model_validate(orjson.loads(raw_value))
        verdict = decide_stub(message)

        await self._producer.produce_verdict(verdict)
        classifier_verdicts_total.labels(decision=verdict.decision).inc()
        classifier_verdict_latency_seconds.observe(verdict.latency_ms / 1000)

        reason = persist_reason(verdict, self._settings.allow_sample_bps)
        if reason is not None:
            await self._store.insert_verdict(verdict, reason)
            classifier_persisted_total.labels(persist_reason=reason).inc()
        else:
            await self._store.upsert_rollup(verdict)
            classifier_rollup_writes_total.inc()


def build_service(settings: ClassifierSettings) -> ClassifierService:
    return ClassifierService(
        settings=settings,
        consumer=PostsConsumer(
            settings.kafka_bootstrap_servers, settings.posts_raw_topic, settings.consumer_group
        ),
        producer=VerdictProducer(settings.kafka_bootstrap_servers, settings.verdicts_topic),
        store=VerdictStore(settings.database_url),
    )
