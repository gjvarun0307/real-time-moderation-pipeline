#!/usr/bin/env python3
"""
Captures a window of live Jetstream traffic verbatim to a zstd-compressed
JSONL file for later replay under load.

Needs the `analysis` extra installed (pip install -e .[analysis]) for zstandard.

Usage:
    python capture_replay.py --duration 7200
    python capture_replay.py --duration 7200 --out-dir data/replay --level 9
"""

import argparse
import asyncio
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets
import zstandard

ENDPOINTS = [
    "wss://jetstream2.us-east.bsky.network/subscribe",
    "wss://jetstream1.us-east.bsky.network/subscribe",
    "wss://jetstream2.us-west.bsky.network/subscribe",
    "wss://jetstream1.us-west.bsky.network/subscribe",
]
PARAMS = "?wantedCollections=app.bsky.feed.post"
RECONNECT_BASE_S = 1
RECONNECT_CAP_S = 60

_stop = False


def _sigint(*_):
    global _stop
    _stop = True
    print("\ninterrupt — closing capture...", file=sys.stderr)


def _endpoint_url(ep: str, cursor: int | None) -> str:
    url = ep + PARAMS
    if cursor is not None:
        url += f"&cursor={cursor}"
    return url


async def capture(duration: int, out_dir: Path, level: int, start_cursor: int | None):
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = out_dir / f"capture_{stamp}.jsonl.zst"
    if out_path.exists():
        sys.exit(f"{out_path} already exists — remove it or rename it before recapturing")

    started = time.time()
    started_local = datetime.now().astimezone()
    deadline = started + duration
    cursor = start_cursor
    last_time_us = None
    total_events = 0
    total_posts = 0
    reconnects = 0
    endpoint_idx = 0
    backoff = RECONNECT_BASE_S

    print(f"local start time: {started_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
          file=sys.stderr)
    print(f"writing to: {out_path}", file=sys.stderr)

    cctx = zstandard.ZstdCompressor(level=level)
    with open(out_path, "wb") as raw_fh, cctx.stream_writer(raw_fh) as fh:
        while not _stop and time.time() < deadline:
            ep = ENDPOINTS[endpoint_idx % len(ENDPOINTS)]
            url = _endpoint_url(ep, cursor)
            print(f"connecting: {url}", file=sys.stderr)
            try:
                async with websockets.connect(url, max_size=None) as ws:
                    backoff = RECONNECT_BASE_S
                    print("connected", file=sys.stderr)
                    while not _stop and time.time() < deadline:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            print("  [30s no data]", file=sys.stderr)
                            continue
                        line = raw if isinstance(raw, str) else raw.decode()
                        fh.write(line.encode("utf-8"))
                        fh.write(b"\n")
                        total_events += 1

                        try:
                            ev = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        t = ev.get("time_us")
                        if isinstance(t, int):
                            last_time_us = t
                        commit = ev.get("commit") or {}
                        if (commit.get("operation") == "create"
                                and commit.get("collection") == "app.bsky.feed.post"):
                            total_posts += 1

                        if total_events % 10000 == 0:
                            elapsed = time.time() - started
                            print(f"  {total_events:>9,} events "
                                  f"({total_posts:,} posts, "
                                  f"{elapsed/60:5.1f} min elapsed)", file=sys.stderr)
            except Exception as e:
                if _stop or time.time() >= deadline:
                    break
                reconnects += 1
                cursor = last_time_us
                endpoint_idx += 1
                print(f"  dropped: {type(e).__name__}: {e} — "
                      f"reconnecting in {backoff}s (cursor={cursor})", file=sys.stderr)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_CAP_S)

    elapsed = time.time() - started
    summary = {
        "started_utc": datetime.fromtimestamp(started, tz=timezone.utc)
            .strftime("%Y-%m-%d %H:%M:%SZ"),
        "started_local": started_local.strftime("%Y-%m-%d %H:%M:%S"),
        "local_hour": started_local.hour,
        "duration_requested_s": duration,
        "elapsed_s": round(elapsed, 1),
        "interrupted": _stop,
        "total_events": total_events,
        "total_posts": total_posts,
        "reconnects": reconnects,
        "raw_file": out_path.name,
    }
    summary_path = out_path.with_suffix("").with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    size_mb = out_path.stat().st_size / 1e6
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"captured {total_events:,} events ({total_posts:,} posts) "
          f"over {elapsed/60:.1f} min, {reconnects} reconnect(s)", file=sys.stderr)
    print(f"  corpus   {out_path}  ({size_mb:.1f} MB compressed)", file=sys.stderr)
    print(f"  summary  {summary_path}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _sigint)
    ap = argparse.ArgumentParser(description="Capture a Jetstream replay corpus")
    ap.add_argument("--duration", type=int, default=7200, help="seconds (default 7200 = 2h)")
    ap.add_argument("--out-dir", type=Path, default=Path("data/replay"))
    ap.add_argument("--level", type=int, default=9, help="zstd compression level")
    ap.add_argument("--cursor", type=int, default=None,
                     help="resume from a unix-microsecond cursor instead of live tail")
    args = ap.parse_args()

    asyncio.run(capture(args.duration, args.out_dir, args.level, args.cursor))
