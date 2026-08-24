"""Temperature scaling, calibration error, and fp32-vs-int8 parity helpers for model export."""

from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import torch
import torch.nn.functional as F


def fit_temperature(
    logits: torch.Tensor, labels: torch.Tensor, lr: float = 0.01, max_iter: int = 50
) -> float:
    """Fits a single scalar temperature minimizing BCE NLL of sigmoid(logits / T) against labels."""
    labels = labels.to(logits.device)
    log_temperature = torch.zeros(1, device=logits.device, requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=lr, max_iter=max_iter)

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        loss = F.binary_cross_entropy_with_logits(logits / log_temperature.exp(), labels)
        loss.backward()  # type: ignore[no-untyped-call]
        return loss

    optimizer.step(closure)  # type: ignore[no-untyped-call]
    return float(log_temperature.exp().item())


def compute_ece(
    probs: npt.NDArray[np.float64], labels: npt.NDArray[np.float64], n_bins: int = 15
) -> float:
    """Expected Calibration Error: |mean predicted probability - mean actual rate| per bin,
    pooled across all labels (each (sample, label) sigmoid output treated as one prediction)."""
    probs_flat = np.asarray(probs).reshape(-1)
    labels_flat = np.asarray(labels).reshape(-1)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

    ece = 0.0
    n = len(probs_flat)
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:], strict=True):
        in_bin = (probs_flat >= lo) & (probs_flat <= hi if hi == 1.0 else probs_flat < hi)
        if not in_bin.any():
            continue
        confidence = probs_flat[in_bin].mean()
        accuracy = labels_flat[in_bin].mean()
        ece += (in_bin.sum() / n) * abs(confidence - accuracy)
    return float(ece)


def parity_ok(
    fp32_scores: dict[str, float], int8_scores: dict[str, float], max_drop: float = 0.01
) -> tuple[bool, dict[str, float]]:
    """Compares label->PR-AUC dicts (as returned by teacher_model.evaluate); fails if any shared
    label's PR-AUC dropped by more than max_drop."""
    deltas = {
        label: int8_scores[label] - fp32_scores[label]
        for label in fp32_scores
        if label in int8_scores
    }
    ok = all(delta >= -max_drop for delta in deltas.values())
    return ok, deltas


class _OnnxSession(Protocol):
    """Structural type for the slice of onnxruntime.InferenceSession this adapter needs."""

    def run(self, output_names: list[str], input_feed: dict[str, Any]) -> list[Any]: ...


class OnnxRuntimeAdapter:
    """Wraps an onnxruntime session so it's usable with teacher_model.evaluate()."""

    def __init__(self, session: _OnnxSession, output_name: str = "logits") -> None:
        self._session = session
        self._output_name = output_name

    def eval(self) -> None:
        pass

    def __call__(self, **kwargs: torch.Tensor) -> Any:
        ort_inputs = {k: v.cpu().numpy() for k, v in kwargs.items()}
        (logits,) = self._session.run([self._output_name], ort_inputs)
        return _LogitsOutput(torch.from_numpy(logits))


class _LogitsOutput:
    def __init__(self, logits: torch.Tensor) -> None:
        self.logits = logits
