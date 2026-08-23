import pandas as pd
import pytest

from training.data_prep import (
    LABEL_COLUMNS,
    add_normalized_text,
    load_english_train,
    load_multilingual_eval,
    split_train_val,
)


def test_load_english_train_renames_comment_text_and_orders_columns(tmp_path):
    csv_path = tmp_path / "train.csv"
    csv_path.write_text(
        "id,comment_text,toxic,severe_toxic,obscene,threat,insult,identity_hate\n"
        "1,hello there,0,0,0,0,0,0\n"
    )
    df = load_english_train(csv_path)
    assert list(df.columns) == ["id", "text", *LABEL_COLUMNS]
    assert df.iloc[0]["text"] == "hello there"


def test_load_english_train_raises_on_missing_columns(tmp_path):
    csv_path = tmp_path / "train.csv"
    csv_path.write_text("id,comment_text,toxic\n1,hello,0\n")
    with pytest.raises(ValueError, match="missing expected columns"):
        load_english_train(csv_path)


def test_load_multilingual_eval_renames_and_orders_columns(tmp_path):
    csv_path = tmp_path / "validation.csv"
    csv_path.write_text("id,comment_text,lang,toxic\n1,hola,es,0\n")
    df = load_multilingual_eval(csv_path)
    assert list(df.columns) == ["id", "text", "lang", "toxic"]
    assert df.iloc[0]["lang"] == "es"


def test_add_normalized_text_drops_rows_left_empty_by_normalization():
    df = pd.DataFrame({"text": ["hello world", "https://example.com/only-a-url"]})
    result = add_normalized_text(df)
    assert list(result["text_normalized"]) == ["hello world"]


def test_split_train_val_is_deterministic_and_disjoint():
    df = pd.DataFrame({"id": range(100), "text": [f"row {i}" for i in range(100)]})
    train_a, val_a = split_train_val(df, val_fraction=0.2, seed=42)
    train_b, val_b = split_train_val(df, val_fraction=0.2, seed=42)

    assert len(val_a) == 20
    assert len(train_a) == 80
    assert set(train_a["id"]) == set(train_b["id"])
    assert set(val_a["id"]) == set(val_b["id"])
    assert set(train_a["id"]).isdisjoint(set(val_a["id"]))


def test_split_train_val_different_seeds_give_different_splits():
    df = pd.DataFrame({"id": range(100), "text": [f"row {i}" for i in range(100)]})
    _, val_a = split_train_val(df, val_fraction=0.2, seed=1)
    _, val_b = split_train_val(df, val_fraction=0.2, seed=2)
    assert set(val_a["id"]) != set(val_b["id"])
