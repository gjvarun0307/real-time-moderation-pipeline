import pandas as pd
import torch
from torch.utils.data import DataLoader

from training.teacher_model import ToxicityDataset, compute_pos_weight, evaluate, make_collate_fn


def test_compute_pos_weight_uses_neg_over_pos_ratio():
    df = pd.DataFrame({"toxic": [1, 0, 0, 0], "threat": [0, 0, 0, 0]})
    weight = compute_pos_weight(df, label_columns=["toxic", "threat"], cap=50.0)
    # toxic: 1 positive, 3 negative -> 3/1 = 3.0
    assert weight[0].item() == 3.0


def test_compute_pos_weight_caps_extreme_imbalance():
    df = pd.DataFrame({"rare": [1] + [0] * 999})
    weight = compute_pos_weight(df, label_columns=["rare"], cap=10.0)
    assert weight[0].item() == 10.0


def test_toxicity_dataset_returns_text_and_label_tensor():
    df = pd.DataFrame(
        {"text_normalized": ["hello", "world"], "toxic": [1, 0], "threat": [0, 0]}
    )
    ds = ToxicityDataset(df, label_columns=["toxic", "threat"])
    text, labels = ds[0]
    assert text == "hello"
    assert torch.equal(labels, torch.tensor([1.0, 0.0]))
    assert len(ds) == 2


class _FakeTokenizer:
    """Stands in for a HF tokenizer without downloading real model assets."""

    def __call__(self, texts, padding, truncation, max_length, return_tensors):
        lens = [min(len(t.split()), max_length) for t in texts]
        width = max(lens) if lens else 1
        input_ids = torch.zeros((len(texts), width), dtype=torch.long)
        attention_mask = torch.zeros((len(texts), width), dtype=torch.long)
        for i, n in enumerate(lens):
            attention_mask[i, :n] = 1
        return {"input_ids": input_ids, "attention_mask": attention_mask}


def test_collate_fn_stacks_labels_and_tokenizes_batch():
    collate = make_collate_fn(_FakeTokenizer(), max_seq_len=8)
    batch = [
        ("one two three", torch.tensor([1.0, 0.0])),
        ("four five", torch.tensor([0.0, 1.0])),
    ]
    out = collate(batch)
    assert out["input_ids"].shape[0] == 2
    assert torch.equal(out["labels"], torch.tensor([[1.0, 0.0], [0.0, 1.0]]))


class _FakeOutput:
    def __init__(self, logits: torch.Tensor) -> None:
        self.logits = logits


class _FakeModel:
    """Deterministic stand-in for a HF sequence classification model."""

    def eval(self) -> None:
        pass

    def __call__(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> _FakeOutput:
        # confident correct logits: matches the label pattern used in the test below
        batch_size = input_ids.shape[0]
        logits = torch.tensor([[4.0, -4.0]] * batch_size)
        return _FakeOutput(logits)


def test_evaluate_returns_perfect_pr_auc_for_a_confidently_correct_model():
    df = pd.DataFrame(
        {
            "text_normalized": ["a", "b", "c", "d"],
            "toxic": [1, 1, 1, 1],
            "threat": [0, 0, 0, 0],
        }
    )
    ds = ToxicityDataset(df, label_columns=["toxic", "threat"])
    loader = DataLoader(
        ds, batch_size=2, collate_fn=make_collate_fn(_FakeTokenizer(), max_seq_len=8)
    )
    scores = evaluate(_FakeModel(), loader, torch.device("cpu"), label_columns=["toxic", "threat"])
    # threat has zero positives in this batch -> skipped, not scored
    assert "threat" not in scores
    assert scores["toxic"] == 1.0
