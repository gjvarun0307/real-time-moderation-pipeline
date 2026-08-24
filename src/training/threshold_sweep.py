"""Routing threshold selection: sweep (tau_lo, tau_hi) pairs against
labeled validation scores, trading escalation rate against end-to-end F1.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import f1_score


@dataclass(frozen=True)
class SweepPoint:
    tau_lo: float
    tau_hi: float
    escalation_rate: float
    f1: float


def evaluate_thresholds(
    scores: np.ndarray, labels: np.ndarray, tau_lo: float, tau_hi: float
) -> tuple[float, float]:
    """Returns (escalation_rate, end_to_end_f1) for one threshold pair.

    In-band predictions are treated as correctly resolved by the
    adjudicator (an oracle assumption) -- this measures how much of the
    pipeline's overall accuracy the escalation band is buying, not Tier
    1's standalone accuracy.
    """
    in_band = (scores >= tau_lo) & (scores <= tau_hi)
    escalation_rate = float(in_band.mean())

    preds = np.where(scores > tau_hi, 1, 0)
    preds[in_band] = labels[in_band]

    f1 = float(f1_score(labels, preds, zero_division=0))
    return escalation_rate, f1


def sweep(
    scores: np.ndarray,
    labels: np.ndarray,
    tau_lo_candidates: list[float],
    tau_hi_candidates: list[float],
) -> list[SweepPoint]:
    points = []
    for tau_lo in tau_lo_candidates:
        for tau_hi in tau_hi_candidates:
            if tau_lo >= tau_hi:
                continue
            escalation_rate, f1 = evaluate_thresholds(scores, labels, tau_lo, tau_hi)
            points.append(SweepPoint(tau_lo, tau_hi, escalation_rate, f1))
    return points


def pick_knee(points: list[SweepPoint], max_escalation_rate: float) -> SweepPoint:
    """Picks the point of diminishing returns among candidates under the
    escalation-rate cap: the point on the (rate, F1) frontier with the
    largest perpendicular distance from the line connecting the
    lowest-rate and highest-rate valid points (classic elbow heuristic).
    """
    valid = [p for p in points if p.escalation_rate <= max_escalation_rate]
    if not valid:
        raise ValueError(f"no threshold pair keeps escalation_rate <= {max_escalation_rate}")

    valid_sorted = sorted(valid, key=lambda p: p.escalation_rate)
    if len(valid_sorted) == 1:
        return valid_sorted[0]

    rates = np.array([p.escalation_rate for p in valid_sorted])
    f1s = np.array([p.f1 for p in valid_sorted])

    rate_range = rates[-1] - rates[0]
    f1_range = f1s.max() - f1s.min()
    norm_rates = (rates - rates[0]) / rate_range if rate_range > 0 else np.zeros_like(rates)
    norm_f1s = (f1s - f1s.min()) / f1_range if f1_range > 0 else np.zeros_like(f1s)

    x1, y1 = norm_rates[0], norm_f1s[0]
    x2, y2 = norm_rates[-1], norm_f1s[-1]
    line_len = float(np.hypot(x2 - x1, y2 - y1))
    if line_len == 0:
        return valid_sorted[int(np.argmax(f1s))]

    numerator = np.abs((y2 - y1) * norm_rates - (x2 - x1) * norm_f1s + x2 * y1 - y2 * x1)
    distances = numerator / line_len
    best_idx = int(np.argmax(distances))
    return valid_sorted[best_idx]
