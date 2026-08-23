#!/usr/bin/env python3
"""
Local data prep for the teacher fine-tune — English train/val split plus the
labeled es/it/tr multilingual eval set, both normalized and written to parquet.

Needs the `training` extra installed (pip install -e ".[training]").

Usage:

    python training/01_data_prep.py
    python training/01_data_prep.py --raw-dir data/training_data --out-dir data/processed
"""

import argparse
from pathlib import Path

from training.data_prep import prepare_datasets

DEFAULT_RAW_DIR = Path("data/training_data")
DEFAULT_OUT_DIR = Path("data/processed")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--val-fraction", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    stats = prepare_datasets(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )

    print(f"\nWrote parquet files to {args.out_dir}/\n")
    print(f"  English raw rows:            {stats['english_raw_rows']:>8}")
    print(f"  dropped (empty after norm):  {stats['english_dropped_empty_after_normalize']:>8}")
    print(f"  train_en.parquet:            {stats['train_en_rows']:>8}")
    print(f"  val_en.parquet:              {stats['val_en_rows']:>8}")
    print()
    print(f"  eval raw rows (es/it/tr):    {stats['eval_raw_rows']:>8}")
    print(f"  dropped (empty after norm):  {stats['eval_dropped_empty_after_normalize']:>8}")
    print(f"  eval_multilingual.parquet:   {stats['eval_multilingual_rows']:>8}")


if __name__ == "__main__":
    main()
