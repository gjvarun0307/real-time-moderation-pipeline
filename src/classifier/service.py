import asyncio
from pathlib import Path

import orjson
import structlog

from classifier.budget_guard import BudgetCounter, BudgetGuard
from classifier.consumer import PostsConsumer
from classifier.decision import decide
from classifier.persistence import VerdictStore, persist_reason
from classifier.producer import VerdictProducer
from classifier.tier0.lexicon import Lexicon, load_lexicons
from classifier.tier1.download import fetch_model_artifacts
from classifier.tier1.model import Tier1Model
from common.config import ClassifierSettings
from common.metrics import (
    classifier_consumer_lag,
    classifier_persisted_total,
    classifier_rollup_writes_total,
    classifier_verdict_latency_seconds,
    classifier_verdicts_total,
)
from common.redis_flag import RedisFlag
from common.schemas import EscalateMessage, PostsRawMessage

logger = structlog.get_logger()

LAG_REPORT_INTERVAL_SECONDS = 10.0


class ClassifierService:
    def __init__(
        self,
        settings: ClassifierSettings,
        consumer: PostsConsumer,
        producer: VerdictProducer,
        store: VerdictStore,
        tier0_lexicons: dict[str, Lexicon],
        tier1: Tier1Model,
        budget_guard: BudgetGuard,
    ) -> None:
        self._settings = settings
        self._consumer = consumer
        self._producer = producer
        self._store = store
        self._tier0_lexicons = tier0_lexicons
        self._tier1 = tier1
        self._budget_guard = budget_guard
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
        await self._budget_guard.close()

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
        result = await decide(
            message,
            lexicons=self._tier0_lexicons,
            tier1=self._tier1,
            budget_guard=self._budget_guard,
            settings=self._settings,
        )

        if isinstance(result, EscalateMessage):
            await self._producer.produce_escalate(result)
            return

        verdict = result
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
    tier0_lexicons = load_lexicons(Path(settings.lexicon_dir))

    version_dir = fetch_model_artifacts(
        settings.tier1_version_tag,
        Path(settings.tier1_model_cache_dir),
        settings.r2_secret_access_key,
    )
    tier1 = Tier1Model(
        model_path=version_dir / "model.onnx",
        tokenizer_dir=version_dir / "tokenizer",
        calibration_path=version_dir / "calibration.json",
        max_seq_len=settings.max_seq_len,
        intra_op_threads=settings.onnx_intra_op_threads,
        version_tag=settings.tier1_version_tag,
    )

    budget_counter = BudgetCounter(settings.redis_url, settings.budget_key_prefix)
    overflow_flag = RedisFlag(
        settings.redis_url, settings.overflow_flag_key, settings.overflow_flag_ttl_seconds
    )
    budget_guard = BudgetGuard(
        budget_counter,
        settings.adjudication_sample_bps,
        settings.adjudication_daily_cap,
        overflow_flag,
    )

    return ClassifierService(
        settings=settings,
        consumer=PostsConsumer(
            settings.kafka_bootstrap_servers, settings.posts_raw_topic, settings.consumer_group
        ),
        producer=VerdictProducer(
            settings.kafka_bootstrap_servers, settings.verdicts_topic, settings.escalate_topic
        ),
        store=VerdictStore(settings.database_url),
        tier0_lexicons=tier0_lexicons,
        tier1=tier1,
        budget_guard=budget_guard,
    )
