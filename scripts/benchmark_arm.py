#!/usr/bin/env python3
"""
Tier 1 ONNX int8 inference benchmark on the target ARM CPU.

Downloads a versioned model export (model.onnx + tokenizer/) from R2, then
times `onnxruntime` CPU inference across batch sizes 1/8/16/32 at a fixed
sequence length, for 1 and 2 intra-op threads. Meant to run on the actual
deployment host, not a dev machine or Colab GPU runtime -- ONNX Runtime's
ARM CPU kernels are a different execution path than CUDA and the numbers
don't transfer.

R2 bucket/account/access-key-id are non-secret and default to the project's
own bucket; the secret key is read from the R2_SECRET_ACCESS_KEY env var
and never accepted as a CLI argument.

Usage:

    export R2_SECRET_ACCESS_KEY=...
    python scripts/benchmark_arm.py --version-tag v1-abc1234
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import boto3
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

R2_BUCKET = "moderation-pipeline"
R2_ACCOUNT_ID = "987b06fd7083dcd8e6e210c4afdedf53"
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_ACCESS_KEY_ID = "3c1b25cb63cc6454ec12dc93c8222185"

BATCH_SIZES = [1, 8, 16, 32]
THREAD_COUNTS = [1, 2]
WARMUP_ITERS = 5
TIMED_ITERS = 30


def fetch_artifacts(version_tag: str, dest_dir: Path) -> Path:
    """Downloads model.onnx and the tokenizer/ prefix for one version tag from R2, skipping
    files already present."""
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not secret_key:
        sys.exit("R2_SECRET_ACCESS_KEY must be set in the environment")

    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=secret_key,
    )

    version_dir = dest_dir / version_tag
    version_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{version_tag}/"

    paginator = s3.get_paginator("list_objects_v2")
    keys = [
        obj["Key"]
        for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix)
        for obj in page.get("Contents", [])
    ]
    if not keys:
        sys.exit(f"no objects found under s3://{R2_BUCKET}/{prefix}")

    for key in keys:
        local_path = version_dir / key[len(prefix) :]
        if local_path.exists():
            continue
        local_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {key} -> {local_path}", file=sys.stderr)
        s3.download_file(R2_BUCKET, key, str(local_path))

    return version_dir


def benchmark_config(
    session: ort.InferenceSession, vocab_size: int, batch_size: int, seq_len: int
) -> dict[str, float]:
    """Times TIMED_ITERS runs of one (batch_size, seq_len) shape after WARMUP_ITERS warmup runs,
    returning latency stats in ms."""
    rng = np.random.default_rng(seed=batch_size)
    input_ids = rng.integers(0, vocab_size, size=(batch_size, seq_len), dtype=np.int64)
    attention_mask = np.ones((batch_size, seq_len), dtype=np.int64)
    feed = {"input_ids": input_ids, "attention_mask": attention_mask}
    output_name = session.get_outputs()[0].name

    for _ in range(WARMUP_ITERS):
        session.run([output_name], feed)

    latencies_ms = []
    for _ in range(TIMED_ITERS):
        start = time.perf_counter()
        session.run([output_name], feed)
        latencies_ms.append((time.perf_counter() - start) * 1000)

    return {
        "p50_ms": statistics.median(latencies_ms),
        "p95_ms": statistics.quantiles(latencies_ms, n=20)[18],
        "mean_ms": statistics.mean(latencies_ms),
        "throughput_items_per_sec": batch_size / (statistics.mean(latencies_ms) / 1000),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--version-tag", required=True, help="e.g. v1-abc1234")
    ap.add_argument("--seq-len", type=int, default=192)
    ap.add_argument(
        "--cache-dir",
        default="benchmark_cache",
        help="local download destination (default: ./benchmark_cache)",
    )
    args = ap.parse_args()

    version_dir = fetch_artifacts(args.version_tag, Path(args.cache_dir))
    model_path = version_dir / "model.onnx"
    tokenizer_dir = version_dir / "tokenizer"
    if not model_path.exists():
        sys.exit(f"{model_path} not found after download")

    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
    vocab_size = tokenizer.vocab_size

    results = []
    for threads in THREAD_COUNTS:
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        for batch_size in BATCH_SIZES:
            stats = benchmark_config(session, vocab_size, batch_size, args.seq_len)
            results.append({"threads": threads, "batch_size": batch_size, **stats})
            print(
                f"threads={threads} batch={batch_size:>2} "
                f"p50={stats['p50_ms']:.2f}ms p95={stats['p95_ms']:.2f}ms "
                f"throughput={stats['throughput_items_per_sec']:.1f}/s",
                file=sys.stderr,
            )

    print(f"\nARM CPU benchmark — {args.version_tag}, seq_len={args.seq_len}\n")
    print("| Threads | Batch | p50 (ms) | p95 (ms) | Mean (ms) | Throughput (items/s) |")
    print("|---|---|---|---|---|---|")
    for r in results:
        print(
            f"| {r['threads']} | {r['batch_size']} | {r['p50_ms']:.2f} | "
            f"{r['p95_ms']:.2f} | {r['mean_ms']:.2f} | {r['throughput_items_per_sec']:.1f} |"
        )

    out_path = version_dir / "arm_benchmark.json"
    out = {"version_tag": args.version_tag, "seq_len": args.seq_len, "results": results}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
