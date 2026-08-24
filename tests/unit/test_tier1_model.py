import json
from pathlib import Path

import numpy as np

from classifier.tier1 import model as model_module
from classifier.tier1.model import LABELS, Tier1Model


class FakeSession:
    def __init__(self, logits: np.ndarray) -> None:
        self._logits = logits
        self.last_input_feed: dict | None = None

    def run(self, output_names, input_feed):
        self.last_input_feed = input_feed
        return [self._logits]


class FakeTokenizer:
    def __init__(self, seq_len: int = 4) -> None:
        self._seq_len = seq_len
        self.last_text: list[str] | None = None

    def __call__(self, texts, **_kwargs):
        self.last_text = texts
        batch = len(texts)
        return {
            "input_ids": np.ones((batch, self._seq_len), dtype=np.int64),
            "attention_mask": np.ones((batch, self._seq_len), dtype=np.int64),
        }


def _build(monkeypatch, tmp_path: Path, logits: np.ndarray, seq_len: int = 4) -> Tier1Model:
    fake_session = FakeSession(logits)
    fake_tokenizer = FakeTokenizer(seq_len=seq_len)
    monkeypatch.setattr(model_module.ort, "InferenceSession", lambda *a, **kw: fake_session)
    monkeypatch.setattr(
        model_module.AutoTokenizer, "from_pretrained", lambda *a, **kw: fake_tokenizer
    )

    calibration_path = tmp_path / "calibration.json"
    calibration_path.write_text(json.dumps({"temperature": 2.0}))

    return Tier1Model(
        model_path=tmp_path / "model.onnx",
        tokenizer_dir=tmp_path / "tokenizer",
        calibration_path=calibration_path,
        max_seq_len=192,
        intra_op_threads=2,
        version_tag="v1-abc",
    )


def test_labels_ordering_and_temperature_applied_before_sigmoid(monkeypatch, tmp_path):
    logits = np.array([[10.0, 0.0, -10.0, 0.0, 0.0, 0.0]])
    tier1 = _build(monkeypatch, tmp_path, logits)

    result = tier1.infer("some text")

    assert list(result.scores) == LABELS
    expected_toxic = 1.0 / (1.0 + np.exp(-(10.0 / 2.0)))
    assert result.scores["toxic"] == expected_toxic
    # not the un-calibrated sigmoid(10.0), which would be ~1.0
    assert result.scores["toxic"] < 0.999


def test_seq_len_reflects_tokenizer_output_shape(monkeypatch, tmp_path):
    logits = np.zeros((1, 6))
    tier1 = _build(monkeypatch, tmp_path, logits, seq_len=17)

    result = tier1.infer("some text")

    assert result.seq_len == 17


def test_model_version_includes_version_tag(monkeypatch, tmp_path):
    tier1 = _build(monkeypatch, tmp_path, np.zeros((1, 6)))
    assert tier1.model_version == "tier1-onnx-v1-abc"
