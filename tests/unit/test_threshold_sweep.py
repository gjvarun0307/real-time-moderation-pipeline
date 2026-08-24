import numpy as np
import pytest

from training.threshold_sweep import SweepPoint, evaluate_thresholds, pick_knee, sweep


def test_perfectly_separated_scores_give_f1_one_outside_the_band():
    labels = np.array([0, 0, 0, 1, 1, 1])
    scores = np.array([0.01, 0.02, 0.03, 0.97, 0.98, 0.99])

    escalation_rate, f1 = evaluate_thresholds(scores, labels, tau_lo=0.1, tau_hi=0.9)

    assert escalation_rate == 0.0
    assert f1 == 1.0


def test_full_band_gives_full_escalation_and_oracle_f1_of_one():
    labels = np.array([0, 1, 0, 1, 1])
    scores = np.array([0.5, 0.5, 0.5, 0.5, 0.5])  # doesn't matter, everything is in-band

    escalation_rate, f1 = evaluate_thresholds(scores, labels, tau_lo=0.0, tau_hi=1.0)

    assert escalation_rate == 1.0
    assert f1 == 1.0  # in-band predictions are oracle-resolved to the true label


def test_misclassified_out_of_band_scores_hurt_f1():
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.99, 0.99, 0.01, 0.01])  # both classes scored backwards

    escalation_rate, f1 = evaluate_thresholds(scores, labels, tau_lo=0.1, tau_hi=0.9)

    assert escalation_rate == 0.0
    assert f1 == 0.0  # every out-of-band prediction is wrong


def test_widening_the_band_can_only_help_or_match_f1():
    rng = np.random.default_rng(0)
    labels = rng.integers(0, 2, size=200)
    scores = np.clip(labels + rng.normal(0, 0.4, size=200), 0, 1)

    _rate_narrow, f1_narrow = evaluate_thresholds(scores, labels, tau_lo=0.3, tau_hi=0.7)
    _rate_wide, f1_wide = evaluate_thresholds(scores, labels, tau_lo=0.1, tau_hi=0.9)

    # a wider band escalates (oracle-resolves) more of the errors a
    # narrower band would have gotten wrong on its own
    assert f1_wide >= f1_narrow


def test_sweep_excludes_invalid_threshold_pairs():
    labels = np.array([0, 1])
    scores = np.array([0.2, 0.8])

    points = sweep(scores, labels, tau_lo_candidates=[0.5], tau_hi_candidates=[0.5, 0.3])

    assert points == []  # tau_lo >= tau_hi in both candidate pairs


def test_sweep_produces_one_point_per_valid_pair():
    labels = np.array([0, 1])
    scores = np.array([0.2, 0.8])

    points = sweep(scores, labels, tau_lo_candidates=[0.1, 0.2], tau_hi_candidates=[0.8, 0.9])

    assert len(points) == 4
    assert all(p.tau_lo < p.tau_hi for p in points)


def test_pick_knee_only_considers_points_under_the_cap():
    points = [
        SweepPoint(tau_lo=0.1, tau_hi=0.9, escalation_rate=0.02, f1=0.70),
        SweepPoint(tau_lo=0.2, tau_hi=0.8, escalation_rate=0.10, f1=0.95),  # over cap
    ]

    chosen = pick_knee(points, max_escalation_rate=0.06)

    assert chosen.escalation_rate == 0.02


def test_pick_knee_raises_when_nothing_satisfies_the_cap():
    points = [SweepPoint(tau_lo=0.2, tau_hi=0.8, escalation_rate=0.5, f1=0.9)]

    with pytest.raises(ValueError, match="escalation_rate"):
        pick_knee(points, max_escalation_rate=0.06)


def test_pick_knee_finds_the_elbow_of_diminishing_returns():
    # F1 climbs fast for a little escalation, then flattens out — the
    # elbow should land near where the climb stops paying off, not at
    # either extreme.
    points = [
        SweepPoint(tau_lo=0.4, tau_hi=0.6, escalation_rate=0.01, f1=0.60),
        SweepPoint(tau_lo=0.3, tau_hi=0.7, escalation_rate=0.02, f1=0.90),
        SweepPoint(tau_lo=0.2, tau_hi=0.8, escalation_rate=0.04, f1=0.93),
        SweepPoint(tau_lo=0.1, tau_hi=0.9, escalation_rate=0.06, f1=0.94),
    ]

    chosen = pick_knee(points, max_escalation_rate=0.06)

    assert chosen.escalation_rate == 0.02  # the elbow, not the cheapest or the most expensive
