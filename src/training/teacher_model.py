"""Dataset, class-weighting, and evaluation helpers for the teacher fine-tune."""

import contextlib
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import pandas as pd
import torch
from sklearn.metrics import average_precision_score
from torch.utils.data import Dataset

from training.data_prep import LABEL_COLUMNS


class _ClassifierModel(Protocol):
    """Structural type for a HF sequence-classification model: callable + eval()."""

    def eval(self) -> Any: ...
    def __call__(self, **kwargs: torch.Tensor) -> Any: ...


def compute_pos_weight(
    df: pd.DataFrame, label_columns: Sequence[str] = LABEL_COLUMNS, cap: float = 50.0
) -> torch.Tensor:
    """BCEWithLogitsLoss pos_weight per label, capped to keep rare-label loss stable."""
    pos = df[list(label_columns)].sum().astype(float)
    neg = len(df) - pos
    weight = (neg / pos.clip(lower=1)).clip(upper=cap)
    return torch.tensor(weight.to_numpy(), dtype=torch.float32)


class ToxicityDataset(Dataset[tuple[str, torch.Tensor]]):
    """Wraps a prepared dataframe (text_normalized + label columns) for tokenized batching."""

    def __init__(self, df: pd.DataFrame, label_columns: Sequence[str] = LABEL_COLUMNS) -> None:
        self.texts = df["text_normalized"].tolist()
        self.labels = df[list(label_columns)].to_numpy(dtype="float32")

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> tuple[str, torch.Tensor]:
        return self.texts[idx], torch.from_numpy(self.labels[idx].copy())


def make_collate_fn(
    tokenizer: Callable[..., Any], max_seq_len: int
) -> Callable[[list[tuple[str, torch.Tensor]]], dict[str, torch.Tensor]]:
    """Builds a collate_fn that tokenizes a batch with dynamic padding to max_seq_len."""

    def collate(batch: list[tuple[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
        texts, labels = zip(*batch, strict=True)
        encoded = tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=max_seq_len,
            return_tensors="pt",
        )
        result: dict[str, torch.Tensor] = dict(encoded)
        result["labels"] = torch.stack(list(labels))
        return result

    return collate


@torch.no_grad()
def evaluate(
    model: _ClassifierModel,
    loader: Any,
    device: torch.device,
    label_columns: Sequence[str] = LABEL_COLUMNS,
) -> dict[str, float]:
    """Runs inference over a dataloader, returning per-label + macro PR-AUC (average precision)."""
    model.eval()
    autocast_ctx: Any = (
        torch.autocast(device_type="cuda", dtype=torch.bfloat16)
        if device.type == "cuda"
        else contextlib.nullcontext()
    )

    all_logits = []
    all_labels = []
    for batch in loader:
        labels = batch.pop("labels")
        batch = {k: v.to(device) for k, v in batch.items()}
        with autocast_ctx:
            logits = model(**batch).logits
        all_logits.append(logits.float().cpu())
        all_labels.append(labels)

    probs = torch.sigmoid(torch.cat(all_logits)).numpy()
    y = torch.cat(all_labels).numpy()

    scores: dict[str, float] = {}
    for i, label in enumerate(label_columns):
        if y[:, i].sum() == 0:
            continue
        scores[label] = float(average_precision_score(y[:, i], probs[:, i]))
    if scores:
        scores["macro_avg"] = sum(scores.values()) / len(scores)
    return scores
