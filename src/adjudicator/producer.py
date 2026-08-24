import time
from typing import Any

import orjson
from aiokafka import AIOKafkaProducer

from common.schemas import Verdict


class AdjudicatorProducer:
    def __init__(self, bootstrap_servers: str, verdicts_topic: str, dlq_topic: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._verdicts_topic = verdicts_topic
        self._dlq_topic = dlq_topic
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
            raise RuntimeError("AdjudicatorProducer.start() was never called")
        value = orjson.dumps(verdict.model_dump())
        key = verdict.author_hash.encode("utf-8")
        await self._producer.send_and_wait(self._verdicts_topic, value=value, key=key)

    async def produce_dlq(self, reason: str, raw_payload: Any) -> None:
        if self._producer is None:
            raise RuntimeError("AdjudicatorProducer.start() was never called")
        body = {"reason": reason, "raw": raw_payload, "dlq_time_us": int(time.time() * 1_000_000)}
        try:
            value = orjson.dumps(body)
        except TypeError:
            value = orjson.dumps({**body, "raw": str(raw_payload)})
        await self._producer.send_and_wait(self._dlq_topic, value=value)
