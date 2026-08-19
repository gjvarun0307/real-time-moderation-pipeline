import structlog

from common.config import IngestSettings
from common.langtags import canonicalize_langs
from common.normalization import normalize
from common.schemas import PostsRawMessage, RawEvent
from ingest.backpressure import AdaptiveQueue
from ingest.cursor_store import CursorStore
from ingest.dedup import BloomDedup, build_post_key
from ingest.filter import Accepted, Rejected, classify
from ingest.firehose import FirehoseSource, JetstreamSource
from ingest.langid import LanguageIdentifier, record_disagreement
from ingest.message import build_message
from ingest.producer import PostsProducer

logger = structlog.get_logger()


class IngestService:
    def __init__(
        self,
        settings: IngestSettings,
        source: FirehoseSource,
        identifier: LanguageIdentifier,
        dedup: BloomDedup,
        queue: "AdaptiveQueue[PostsRawMessage]",
        producer: PostsProducer,
        cursor_store: CursorStore,
    ) -> None:
        self._settings = settings
        self._source = source
        self._identifier = identifier
        self._dedup = dedup
        self._queue = queue
        self._producer = producer
        self._cursor_store = cursor_store
        self._ready = False

    async def start(self) -> None:
        await self._producer.start()
        self._ready = True

    async def stop(self) -> None:
        self._ready = False
        await self._producer.stop()
        await self._cursor_store.close()

    def is_ready(self) -> bool:
        return self._ready

    async def run_ingest_loop(self) -> None:
        async for event in self._source.stream():
            try:
                await self._handle_event(event)
            except Exception:
                logger.exception("ingest_event_handling_failed", did=event.did)

    async def run_produce_loop(self) -> None:
        while True:
            message = await self._queue.queue.get()
            await self._producer.produce_post(message)

    async def _handle_event(self, event: RawEvent) -> None:
        result = classify(event, self._settings.wanted_collections)

        if isinstance(result, Rejected):
            if result.is_dlq:
                await self._producer.produce_dlq(result.reason, event.model_dump())
            return

        assert isinstance(result, Accepted)
        post_uri = build_post_key(event.did, result.commit.collection, result.commit.rkey)
        if self._dedup.is_duplicate(post_uri):
            return

        text_normalized = normalize(result.post.text)
        declared_canon = canonicalize_langs(result.post.langs)
        declared_raw = result.post.langs[0] if result.post.langs else None
        lang_predicted, lang_confidence = self._identifier.predict(
            text_normalized or result.post.text
        )
        record_disagreement(declared_canon, lang_predicted)

        message = build_message(
            event=event,
            accepted=result,
            text_normalized=text_normalized,
            lang_declared=declared_canon[0] if declared_canon else None,
            lang_declared_raw=declared_raw,
            lang_predicted=lang_predicted,
            lang_confidence=lang_confidence,
            salt=self._settings.author_hash_salt,
        )
        self._queue.offer(post_uri, message)


def build_service(settings: IngestSettings) -> IngestService:
    cursor_store = CursorStore(settings.redis_url, settings.cursor_redis_key)
    identifier = (
        LanguageIdentifier(model_path=settings.fasttext_model_path)
        if settings.fasttext_model_path
        else LanguageIdentifier()
    )
    return IngestService(
        settings=settings,
        source=JetstreamSource(settings, cursor_store),
        identifier=identifier,
        dedup=BloomDedup(),
        queue=AdaptiveQueue(maxsize=settings.queue_max),
        producer=PostsProducer(
            settings.kafka_bootstrap_servers, settings.posts_raw_topic, settings.dlq_topic
        ),
        cursor_store=cursor_store,
    )
