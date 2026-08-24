import orjson
from aiokafka import AIOKafkaProducer

from common.schemas import EscalateMessage, Verdict


class VerdictProducer:
    def __init__(self, bootstrap_servers: str, verdicts_topic: str, escalate_topic: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._verdicts_topic = verdicts_topic
        self._escalate_topic = escalate_topic
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        # AIOKafkaProducer needs a running event loop at construction
        # time, so it's built here rather than in __init__.
        self._producer = AIOKafkaProducer(bootstrap_servers=self._bootstrap_servers)
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()

    async def produce_verdict(self, verdict: Verdict) -> None:
        if self._producer is None:
            raise RuntimeError("VerdictProducer.start() was never called")
        value = orjson.dumps(verdict.model_dump())
        key = verdict.author_hash.encode("utf-8")
        await self._producer.send_and_wait(self._verdicts_topic, value=value, key=key)

    async def produce_escalate(self, message: EscalateMessage) -> None:
        if self._producer is None:
            raise RuntimeError("VerdictProducer.start() was never called")
        value = orjson.dumps(message.model_dump())
        key = message.author_hash.encode("utf-8")
        await self._producer.send_and_wait(self._escalate_topic, value=value, key=key)
