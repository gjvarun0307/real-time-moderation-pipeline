from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord


class EscalateConsumer:
    def __init__(
        self, bootstrap_servers: str, topic: str, group_id: str, max_poll_records: int
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._max_poll_records = max_poll_records
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        # Needs a running event loop, so construction happens here rather
        # than in __init__.
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            max_poll_records=self._max_poll_records,
        )
        await self._consumer.start()

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()

    async def messages(self) -> AsyncIterator[ConsumerRecord]:
        if self._consumer is None:
            raise RuntimeError("EscalateConsumer.start() was never called")
        async for record in self._consumer:
            yield record

    async def commit(self) -> None:
        if self._consumer is None:
            raise RuntimeError("EscalateConsumer.start() was never called")
        await self._consumer.commit()

    async def current_lag(self) -> int:
        if self._consumer is None:
            return 0
        total = 0
        for tp in self._consumer.assignment():
            highwater = self._consumer.highwater(tp)
            position = await self._consumer.position(tp)
            if highwater is not None and position is not None:
                total += max(0, highwater - position)
        return total
