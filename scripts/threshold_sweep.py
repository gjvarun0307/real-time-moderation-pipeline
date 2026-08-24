#!/usr/bin/env python3
"""
Chooses Tier 1's routing thresholds (tau_lo, tau_hi) by explicit
optimization against labeled validation data, instead of the spec-default
placeholders currently in ClassifierSettings.

Runs the real deployed Tier 1 model (single-item inference, matching
production exactly) over data/processed/val_en.parquet, sweeps a grid of
threshold pairs, and picks the knee of the escalation-rate-vs-F1 curve
subject to escalation_rate <= --max-escalation-rate (spec's 0.06 cap).
Saves a plot for the writeup and prints the recommended values.

Needs R2_SECRET_ACCESS_KEY in the environment to fetch the model.

Usage:

    export R2_SECRET_ACCESS_KEY=...
    python scripts/threshold_sweep.py
    python scripts/threshold_sweep.py --limit 2000  # faster iteration
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "src")

from classifier.tier1.download import fetch_model_artifacts  # noqa: E402
from classifier.tier1.model import Tier1Model  # noqa: E402
from training.threshold_sweep import pick_knee, sweep  # noqa: E402

DEFAULT_TAU_LO_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
DEFAULT_TAU_HI_GRID = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]


def score_validation_set(model: Tier1Model, texts: list[str]) -> np.ndarray:
    scores = np.empty(len(texts), dtype=np.float64)
    for i, text in enumerate(texts):
        scores[i] = model.infer(text).scores["toxic"]
        if (i + 1) % 1000 == 0:
            print(f"  scored {i + 1}/{len(texts)}", file=sys.stderr)
    return scores


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--val-path", default="data/processed/val_en.parquet")
    ap.add_argument("--version-tag", default="v1-70dee6e")
    ap.add_argument("--cache-dir", default="benchmark_cache")
    ap.add_argument("--max-seq-len", type=int, default=192)
    ap.add_argument("--intra-op-threads", type=int, default=2)
    ap.add_argument("--max-escalation-rate", type=float, default=0.06)
    ap.add_argument("--limit", type=int, default=None, help="subsample for faster iteration")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--plot-path", default="docs/threshold_sweep.png")
    args = ap.parse_args()

    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    if not secret_key:
        sys.exit("R2_SECRET_ACCESS_KEY must be set in the environment")

    df = pd.read_parquet(args.val_path)
    if args.limit is not None and args.limit < len(df):
        df = df.sample(n=args.limit, random_state=args.seed).reset_index(drop=True)
    print(f"loaded {len(df)} labeled validation rows from {args.val_path}", file=sys.stderr)

    version_dir = fetch_model_artifacts(args.version_tag, Path(args.cache_dir), secret_key)
    model = Tier1Model(
        model_path=version_dir / "model.onnx",
        tokenizer_dir=version_dir / "tokenizer",
        calibration_path=version_dir / "calibration.json",
        max_seq_len=args.max_seq_len,
        intra_op_threads=args.intra_op_threads,
        version_tag=args.version_tag,
    )

    print("scoring validation set (this can take a while)...", file=sys.stderr)
    scores = score_validation_set(model, df["text_normalized"].tolist())
    labels = df["toxic"].to_numpy()

    points = sweep(scores, labels, DEFAULT_TAU_LO_GRID, DEFAULT_TAU_HI_GRID)
    chosen = pick_knee(points, max_escalation_rate=args.max_escalation_rate)
    tau_mid = (chosen.tau_lo + chosen.tau_hi) / 2

    print(f"\nThreshold sweep — {args.version_tag}, {len(df)} validation rows\n")
    print("| tau_lo | tau_hi | escalation_rate | F1 |")
    print("|---|---|---|---|")
    for p in sorted(points, key=lambda p: p.escalation_rate):
        marker = " **<- chosen**" if p is chosen else ""
        print(f"| {p.tau_lo:.2f} | {p.tau_hi:.2f} | {p.escalation_rate:.4f} | {p.f1:.4f} |{marker}")

    print(f"\nChosen (knee, escalation_rate <= {args.max_escalation_rate}):")
    print(f"  tau_lo = {chosen.tau_lo}")
    print(f"  tau_hi = {chosen.tau_hi}")
    print(f"  tau_mid = {tau_mid} (midpoint, unchanged derivation)")
    print(f"  escalation_rate = {chosen.escalation_rate:.4f}")
    print(f"  end-to-end F1 (oracle-resolved band) = {chosen.f1:.4f}")
    print(
        "\nUpdate ClassifierSettings' tau_lo/tau_hi/tau_mid defaults in "
        "src/common/config.py to these values (or set CLASSIFIER_TAU_LO / "
        "CLASSIFIER_TAU_HI / CLASSIFIER_TAU_MID env vars on the deployment)."
    )

    _save_plot(points, chosen, args.max_escalation_rate, args.plot_path)


def _save_plot(points, chosen, max_escalation_rate: float, plot_path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rates = [p.escalation_rate for p in points]
    f1s = [p.f1 for p in points]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(rates, f1s, alpha=0.6, label="threshold pairs")
    ax.scatter(
        [chosen.escalation_rate], [chosen.f1], color="red", s=100, zorder=5, label="chosen (knee)"
    )
    ax.axvline(
        max_escalation_rate, color="gray", linestyle="--", label=f"cap ({max_escalation_rate})"
    )
    ax.set_xlabel("Escalation rate")
    ax.set_ylabel("End-to-end F1 (oracle-resolved band)")
    ax.set_title("Routing threshold sweep: escalation rate vs. F1")
    ax.legend()
    fig.tight_layout()

    Path(plot_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=150)
    print(f"\nwrote {plot_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
