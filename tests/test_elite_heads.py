"""Tests for models.elite_heads — PodiumHead and WinnerHead."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from models.elite_features import FEATURE_COLUMNS
from models.elite_heads import PodiumHead, WinnerHead, evaluate_head


def _make_feature_frame(n_rounds: int = 6, drivers_per_round: int = 12) -> tuple[pd.DataFrame, pd.Series]:
    """Synth a training frame with a clean elite-signal pattern.

    Driver 'A' is the dominant winner (high podium_rate). Driver 'B' is a
    podium regular. The rest are field. Outcomes are deterministic from
    predicted_position so the classifier has signal to learn.
    """
    rng = np.random.default_rng(42)
    rows: list[dict] = []
    actuals: list[int] = []
    drivers = [f"D{i:02d}" for i in range(drivers_per_round)]
    drivers[0] = "A"
    drivers[1] = "B"
    for rnd in range(1, n_rounds + 1):
        # Shuffle some noise into predicted_position
        order = list(range(drivers_per_round))
        rng.shuffle(order)
        for slot, drv in enumerate(drivers):
            predicted_pos = order.index(slot) + 1
            # actual leaders: A is podium ~80%, B is podium ~60%
            if drv == "A":
                actual = 1 if rnd % 2 == 0 else 2
            elif drv == "B":
                actual = 2 if rnd % 3 == 0 else 3
            else:
                actual = max(
                    4,
                    min(drivers_per_round, predicted_pos + int(rng.normal(0, 1.5))),
                )
            # Driver-history rates (synth — what the real builder would compute)
            podium_rate_5 = (
                0.8 if drv == "A" else (0.5 if drv == "B" else 0.1)
            )
            podium_rate_season = podium_rate_5
            winner_rate_season = (
                0.5 if drv == "A" else (0.0 if drv == "B" else 0.0)
            )
            circuit_rate = float("nan") if rnd <= 2 else podium_rate_5
            quali_dom = float(predicted_pos - 1) * 0.1
            rows.append(
                {
                    "driver": drv,
                    "season": 2024,
                    "round": rnd,
                    "driver_podium_rate_5": podium_rate_5,
                    "driver_podium_rate_season": podium_rate_season,
                    "driver_winner_rate_season": winner_rate_season,
                    "driver_circuit_podium_rate": circuit_rate,
                    "qualifying_dominance": quali_dom,
                    "predicted_position": float(predicted_pos),
                    "predicted_lap_time_rank": float(predicted_pos),
                }
            )
            actuals.append(actual)
    return pd.DataFrame(rows), pd.Series(actuals, dtype=int)


def test_podium_head_fits_and_predicts():
    feats, actuals = _make_feature_frame()
    head = PodiumHead(estimator="logreg")
    head.fit(feats, actuals)
    probs = head.predict_proba(feats)
    assert probs.shape == (len(feats),)
    assert np.all((probs >= 0.0) & (probs <= 1.0))


def test_winner_head_fits_and_predicts():
    feats, actuals = _make_feature_frame(n_rounds=8)
    head = WinnerHead(estimator="logreg")
    head.fit(feats, actuals)
    probs = head.predict_proba(feats)
    assert probs.shape == (len(feats),)
    assert np.all((probs >= 0.0) & (probs <= 1.0))


def test_podium_head_average_probability_calibration_sane():
    """Mean P(podium) across the field in a single round shouldn't be wildly
    off from 3/N. Tolerance is loose because the test data is synth — we just
    want to catch obviously-broken outputs."""
    feats, actuals = _make_feature_frame(n_rounds=12, drivers_per_round=22)
    head = PodiumHead(estimator="logreg")
    head.fit(feats, actuals)
    probs = head.predict_proba(feats)
    feats = feats.copy()
    feats["prob"] = probs
    avg_per_round = feats.groupby(["season", "round"])["prob"].mean().mean()
    # Acceptable band: 0.05 .. 0.30 (target ~3/22 = 0.136)
    assert 0.05 <= avg_per_round <= 0.30, (
        f"avg P(podium) {avg_per_round:.3f} outside sane range"
    )


def test_head_learns_signal():
    """The dominant driver A's mean P(podium) on training data must exceed
    the rest of the field's average."""
    feats, actuals = _make_feature_frame()
    head = PodiumHead(estimator="logreg")
    head.fit(feats, actuals)
    probs = head.predict_proba(feats)
    feats_with = feats.copy()
    feats_with["prob"] = probs
    a_mean = feats_with[feats_with["driver"] == "A"]["prob"].mean()
    rest_mean = feats_with[~feats_with["driver"].isin(["A", "B"])]["prob"].mean()
    assert a_mean > rest_mean, (
        f"A's prob {a_mean:.3f} should beat rest mean {rest_mean:.3f}"
    )


def test_save_and_load_round_trip(tmp_path: Path):
    feats, actuals = _make_feature_frame()
    head = PodiumHead(estimator="logreg")
    head.fit(feats, actuals)
    p1 = head.predict_proba(feats)

    path = tmp_path / "podium_head.joblib"
    head.save(path)
    loaded = PodiumHead.load(path)
    p2 = loaded.predict_proba(feats)
    np.testing.assert_allclose(p1, p2)


def test_evaluate_head_returns_metrics():
    feats, actuals = _make_feature_frame()
    head = PodiumHead(estimator="logreg")
    head.fit(feats, actuals)
    metrics = evaluate_head(head, feats, actuals, k_for_precision=3)
    assert "auc" in metrics
    assert "brier" in metrics
    assert "precision_at_3" in metrics
    assert 0.0 <= metrics["brier"] <= 1.0
    assert metrics["n_rows"] == len(feats)
    assert metrics["n_rounds"] >= 1


def test_feature_importance_sums_to_one():
    feats, actuals = _make_feature_frame()
    head = PodiumHead(estimator="logreg")
    head.fit(feats, actuals)
    imps = head.feature_importance()
    assert set(imps.keys()) == set(FEATURE_COLUMNS)
    total = sum(imps.values())
    assert math.isclose(total, 1.0, abs_tol=1e-6), (
        f"feature importance sum {total} != 1"
    )


def test_gbm_estimator_path():
    """Ensure the GBM alternative also fits + predicts."""
    feats, actuals = _make_feature_frame(n_rounds=10)
    head = PodiumHead(estimator="gbm")
    head.fit(feats, actuals)
    probs = head.predict_proba(feats)
    assert np.all((probs >= 0.0) & (probs <= 1.0))


def test_predict_before_fit_raises():
    head = PodiumHead()
    feats, _ = _make_feature_frame(n_rounds=2)
    with pytest.raises(RuntimeError):
        head.predict_proba(feats)
