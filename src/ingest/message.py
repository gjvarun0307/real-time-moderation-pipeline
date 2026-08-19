import hashlib
import time
from typing import Literal

import emoji
from uuid6 import uuid7

from common.schemas import PostsRawMessage, RawEvent
from ingest.dedup import build_post_key
from ingest.filter import Accepted


def hash_author(did: str, salt: str) -> str:
    return hashlib.sha256((salt + did).encode("utf-8")).hexdigest()[:32]


def build_message(
    event: RawEvent,
    accepted: Accepted,
    text_normalized: str,
    lang_declared: str | None,
    lang_declared_raw: str | None,
    lang_predicted: str,
    lang_confidence: float,
    salt: str,
    source: Literal["live", "replay"] = "live",
) -> PostsRawMessage:
    commit, post = accepted.commit, accepted.post
    return PostsRawMessage(
        id=str(uuid7()),
        post_uri=build_post_key(event.did, commit.collection, commit.rkey),
        author_hash=hash_author(event.did, salt),
        text=post.text,
        text_normalized=text_normalized,
        lang_declared=lang_declared,
        lang_declared_raw=lang_declared_raw,
        lang_predicted=lang_predicted,
        lang_confidence=lang_confidence,
        event_time_us=event.time_us,
        ingest_time_us=int(time.time() * 1_000_000),
        char_len=len(post.text),
        has_emoji=emoji.emoji_count(post.text) > 0,
        source=source,
        schema_version=2,
    )
