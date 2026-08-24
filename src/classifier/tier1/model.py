"""Tier 1 single-item ONNX inference.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

LABELS = ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate"]


@dataclass(frozen=True)
class Tier1Result:
    scores: dict[str, float]
    seq_len: int


class Tier1Model:
    """Wraps an ONNX int8 session plus its tokenizer and calibration
    temperature for single-item multi-label toxicity scoring."""

    def __init__(
        self,
        model_path: Path,
        tokenizer_dir: Path,
        calibration_path: Path,
        max_seq_len: int,
        intra_op_threads: int,
        version_tag: str,
    ) -> None:
        options = ort.SessionOptions()
        options.intra_op_num_threads = intra_op_threads
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
        self._temperature = json.loads(calibration_path.read_text())["temperature"]
        self._max_seq_len = max_seq_len
        self.model_version = f"tier1-onnx-{version_tag}"

    def infer(self, text: str) -> Tier1Result:
        """Synchronous single-item inference — blocking; the caller must
        offload this off the event loop. Applies
        sigmoid(logit / calibration_temperature), never raw sigmoid."""
        inputs = self._tokenizer(
            [text],
            padding=True,
            truncation=True,
            max_length=self._max_seq_len,
            return_tensors="np",
        )
        (logits,) = self._session.run(
            ["logits"],
            {"input_ids": inputs["input_ids"], "attention_mask": inputs["attention_mask"]},
        )
        probs = 1.0 / (1.0 + np.exp(-(logits[0] / self._temperature)))
        return Tier1Result(
            scores=dict(zip(LABELS, probs.tolist(), strict=True)),
            seq_len=int(inputs["input_ids"].shape[1]),
        )
