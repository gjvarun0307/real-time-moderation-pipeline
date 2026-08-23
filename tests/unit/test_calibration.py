import numpy as np
import pytest
import torch

from training.calibration import OnnxRuntimeAdapter, compute_ece, fit_temperature, parity_ok


def test_fit_temperature_softens_overconfident_logits():
    torch.manual_seed(0)
    true_logits = torch.randn(500, 3)
    labels = torch.bernoulli(torch.sigmoid(true_logits))
    overconfident_logits = true_logits * 5.0  # artificially scaled up -> overconfident

    temperature = fit_temperature(overconfident_logits, labels)
    assert temperature > 1.0


def test_compute_ece_near_zero_for_calibrated_probabilities():
    rng = np.random.default_rng(0)
    probs = rng.uniform(0, 1, size=(2000, 1))
    labels = rng.binomial(1, probs).astype(float)
    ece = compute_ece(probs, labels, n_bins=10)
    assert ece < 0.05


def test_compute_ece_high_for_miscalibrated_probabilities():
    probs = np.full((200, 1), 0.95)
    labels = np.zeros((200, 1))
    ece = compute_ece(probs, labels, n_bins=10)
    assert ece > 0.8


def test_parity_ok_true_when_within_threshold():
    fp32 = {"toxic": 0.90, "macro_avg": 0.80}
    int8 = {"toxic": 0.895, "macro_avg": 0.795}
    ok, deltas = parity_ok(fp32, int8, max_drop=0.01)
    assert ok
    assert deltas["toxic"] == pytest.approx(-0.005)


def test_parity_ok_false_when_drop_exceeds_threshold():
    fp32 = {"toxic": 0.90}
    int8 = {"toxic": 0.85}
    ok, deltas = parity_ok(fp32, int8, max_drop=0.01)
    assert not ok
    assert deltas["toxic"] == pytest.approx(-0.05)


def test_parity_ok_improvement_still_passes():
    fp32 = {"toxic": 0.90}
    int8 = {"toxic": 0.92}
    ok, _ = parity_ok(fp32, int8, max_drop=0.01)
    assert ok


class _FakeSession:
    def __init__(self, logits: torch.Tensor) -> None:
        self._logits = logits

    def run(self, output_names, input_feed):
        return [self._logits.numpy()]


def test_onnx_runtime_adapter_exposes_logits_like_a_hf_model():
    logits = torch.tensor([[1.0, -1.0], [0.5, 0.5]])
    adapter = OnnxRuntimeAdapter(_FakeSession(logits))
    adapter.eval()  # should be a no-op, not raise

    output = adapter(
        input_ids=torch.zeros((2, 4), dtype=torch.long),
        attention_mask=torch.ones((2, 4), dtype=torch.long),
    )
    assert torch.equal(output.logits, logits)
