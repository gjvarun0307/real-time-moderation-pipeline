from ingest.cursor_store import clamp_cursor

ONE_HOUR_US = 3600 * 1_000_000


def test_clamp_cursor_none_stays_none():
    assert clamp_cursor(None, now_us=10 * ONE_HOUR_US, max_staleness_seconds=3600) is None


def test_clamp_cursor_recent_cursor_passes_through_unchanged():
    now_us = 10 * ONE_HOUR_US
    recent_cursor = now_us - 100  # 100us old, well within the window
    assert clamp_cursor(recent_cursor, now_us, max_staleness_seconds=3600) == recent_cursor


def test_clamp_cursor_stale_cursor_gets_floored():
    now_us = 10 * ONE_HOUR_US
    stale_cursor = 1 * ONE_HOUR_US  # 9 hours old
    result = clamp_cursor(stale_cursor, now_us, max_staleness_seconds=3600)
    assert result == now_us - ONE_HOUR_US
    assert result > stale_cursor
