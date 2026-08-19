from common.schemas import RawEvent
from ingest.filter import SCHEMA_INVALID, Accepted, DropReason, Rejected, classify

WANTED = "app.bsky.feed.post"


def _event(**overrides) -> RawEvent:
    base = {
        "did": "did:plc:abc123",
        "time_us": 1725911162329308,
        "kind": "commit",
        "commit": {
            "rev": "abc",
            "operation": "create",
            "collection": "app.bsky.feed.post",
            "rkey": "xyz",
            "cid": "bafy...",
            "record": {"text": "hello world", "langs": ["en"]},
        },
    }
    base.update(overrides)
    return RawEvent.model_validate(base)


def test_valid_post_is_accepted():
    result = classify(_event(), WANTED)
    assert isinstance(result, Accepted)
    assert result.post.text == "hello world"
    assert result.commit.operation == "create"


def test_non_commit_kind_is_dropped_not_dlqd():
    result = classify(_event(kind="identity", commit=None), WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == DropReason.NOT_COMMIT
    assert result.is_dlq is False


def test_missing_commit_on_commit_kind_is_schema_invalid():
    result = classify(_event(commit=None), WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == SCHEMA_INVALID
    assert result.is_dlq is True


def test_delete_operation_is_dropped_with_op_specific_reason():
    event = _event(
        commit={"rev": "abc", "operation": "delete", "collection": WANTED, "rkey": "xyz"}
    )
    result = classify(event, WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == "op_delete"
    assert result.is_dlq is False


def test_update_operation_is_dropped_with_op_specific_reason():
    event = _event(
        commit={
            "rev": "abc",
            "operation": "update",
            "collection": WANTED,
            "rkey": "xyz",
            "record": {"text": "edited"},
        }
    )
    result = classify(event, WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == "op_update"


def test_wrong_collection_is_dropped():
    event = _event(
        commit={
            "rev": "abc",
            "operation": "create",
            "collection": "app.bsky.feed.like",
            "rkey": "xyz",
            "record": {"text": "n/a"},
        }
    )
    result = classify(event, WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == DropReason.WRONG_COLLECTION


def test_create_without_record_is_schema_invalid():
    event = _event(
        commit={"rev": "abc", "operation": "create", "collection": WANTED, "rkey": "xyz"}
    )
    result = classify(event, WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == SCHEMA_INVALID
    assert result.is_dlq is True


def test_empty_text_after_strip_is_dropped():
    event = _event(
        commit={
            "rev": "abc",
            "operation": "create",
            "collection": WANTED,
            "rkey": "xyz",
            "record": {"text": "   "},
        }
    )
    result = classify(event, WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == DropReason.EMPTY_TEXT
    assert result.is_dlq is False


def test_malformed_commit_shape_is_schema_invalid():
    # missing required fields (rev, rkey) on the commit object
    event = _event(commit={"operation": "create", "collection": WANTED})
    result = classify(event, WANTED)
    assert isinstance(result, Rejected)
    assert result.reason == SCHEMA_INVALID
    assert result.is_dlq is True
