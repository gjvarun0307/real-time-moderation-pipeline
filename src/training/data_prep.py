"""Loading, normalization, and splitting for the Jigsaw training datasets."""

from pathlib import Path

import pandas as pd

from common.normalization import normalize

LABEL_COLUMNS = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]


def load_english_train(path: Path) -> pd.DataFrame:
    """Load the merged English Jigsaw train set (id, text, 6 multi-label columns)."""
    df = pd.read_csv(path)
    missing = ({"id", "comment_text", *LABEL_COLUMNS}) - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing expected columns: {sorted(missing)}")
    df = df.rename(columns={"comment_text": "text"})
    return df[["id", "text", *LABEL_COLUMNS]]


def load_multilingual_eval(path: Path) -> pd.DataFrame:
    """Load the labeled es/it/tr validation set (id, text, lang, single toxic label)."""
    df = pd.read_csv(path)
    missing = {"id", "comment_text", "lang", "toxic"} - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing expected columns: {sorted(missing)}")
    df = df.rename(columns={"comment_text": "text"})
    return df[["id", "text", "lang", "toxic"]]


def add_normalized_text(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `text_normalized` column and drop rows left empty by normalization."""
    df = df.copy()
    df["text_normalized"] = df["text"].astype(str).map(normalize)
    return df[df["text_normalized"] != ""].reset_index(drop=True)


def split_train_val(
    df: pd.DataFrame, val_fraction: float = 0.1, seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministically shuffle-split a frame into (train, val) by row fraction."""
    shuffled = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    val_size = int(len(shuffled) * val_fraction)
    return shuffled.iloc[val_size:].reset_index(drop=True), shuffled.iloc[:val_size].reset_index(
        drop=True
    )


def prepare_datasets(
    raw_dir: Path, out_dir: Path, val_fraction: float = 0.1, seed: int = 42
) -> dict[str, int]:
    """Run the full local data-prep pass and write train/val/eval parquet files."""
    ml_dir = raw_dir / "jigsaw-multilingual-toxic-comment-classification"

    english_raw = load_english_train(ml_dir / "jigsaw-toxic-comment-train.csv")
    english = add_normalized_text(english_raw)
    train_en, val_en = split_train_val(english, val_fraction=val_fraction, seed=seed)

    eval_raw = load_multilingual_eval(ml_dir / "validation.csv")
    eval_multilingual = add_normalized_text(eval_raw)

    out_dir.mkdir(parents=True, exist_ok=True)
    train_en.to_parquet(out_dir / "train_en.parquet", index=False)
    val_en.to_parquet(out_dir / "val_en.parquet", index=False)
    eval_multilingual.to_parquet(out_dir / "eval_multilingual.parquet", index=False)

    return {
        "english_raw_rows": len(english_raw),
        "english_dropped_empty_after_normalize": len(english_raw) - len(english),
        "train_en_rows": len(train_en),
        "val_en_rows": len(val_en),
        "eval_raw_rows": len(eval_raw),
        "eval_dropped_empty_after_normalize": len(eval_raw) - len(eval_multilingual),
        "eval_multilingual_rows": len(eval_multilingual),
    }
