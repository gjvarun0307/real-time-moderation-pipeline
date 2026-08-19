from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import ConsumerRecord


class PostsConsumer:
    def __init__(self, bootstrap_servers: str, topic: str, group_id: str) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._group_id = group_id
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        # Same constraint as AIOKafkaProducer: needs a running event loop,
        # so construction happens here rather than in __init__.
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await self._consumer.start()

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()

    async def messages(self) -> AsyncIterator[ConsumerRecord]:
        if self._consumer is None:
            raise RuntimeError("PostsConsumer.start() was never called")
        async for record in self._consumer:
            yield record

    async def commit(self) -> None:
        if self._consumer is None:
            raise RuntimeError("PostsConsumer.start() was never called")
        await self._consumer.commit()

    async def current_lag(self) -> int:
        """Summed lag across currently assigned partitions.

        `highwater()` is a cheap local read of the last-known broker
        offset; `position()` is the documented async call for this
        consumer's own current offset, so an accurate reading needs one
        broker round-trip per assigned partition — fine at the interval
        a metrics-reporting loop calls this on, not fine per-message.
        """
        if self._consumer is None:
            return 0
        total = 0
        for tp in self._consumer.assignment():
            highwater = self._consumer.highwater(tp)
            position = await self._consumer.position(tp)
            if highwater is not None and position is not None:
                total += max(0, highwater - position)
        return total
