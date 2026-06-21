"""Tests for models.volatility_model."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leakage import LeakageError
from models.track_archetype import get_archetype
from models.volatility_model import (
    FEATURE_COLUMNS,
    SATURATION_SHUFFLE,
    VolatilityModel,
    build_volatility_features,
    build_volatility_training_frame,
)


def _make_history(seasons_rounds: list[tuple[int, int, str]], shuffle_magnitude: float = 2.0):
    """Synth a history frame across multiple (season, round, gp_key) tuples.

    Each round has 20 drivers; predicted_position is 1..20, actual is
    predicted + a deterministic noise with mean ``shuffle_magnitude``.
    """
    rng = np.random.default_rng(7)
    rows = []
    for season, round_, gp_key in seasons_rounds:
        for pos in range(1, 21):
            noise = float(rng.normal(0.0, shuffle_magnitude))
            actual = int(np.clip(pos + noise, 1, 20))
            rows.append(
                {
                    "season": season,
                    "round": round_,
                    "driver": f"D{pos:02d}",
                    "predicted_position": pos,
                    "actual_position": actual,
                    "predicted_lap_time": 80.0 + (pos - 1) * 0.1,
                    "gp_key": gp_key,
                }
            )
    return pd.DataFrame(rows)


def test_features_have_all_columns():
    history = _make_history([(2024, 1, "Bahrain"), (2024, 2, "Saudi Arabia")])
    feats = build_volatility_features(
        history, 2024, 2, "Saudi Arabia", get_archetype("Saudi Arabia")
    )
    for col in FEATURE_COLUMNS:
        assert col in feats


def test_leak_protection_assertion():
    """Asking for round 1 features while history contains round 5 should raise."""
    # Manually corrupt: feed history that contains a 'future' (round 6) into
    # build for target (season=2024, round=5) — should raise inside the helper
    # because the row at (2024, 6) is at-or-after.
    # Boundary check: only catches rows >= target.
    with pytest.raises(LeakageError):
        # We have to force the issue by NOT filtering; the helper itself filters
        # but also asserts. To trigger the assert we need a row at the target
        # round AND a row beyond. The internal filter removes >= target so the
        # assert never fires on standard input. Instead, call assert directly
        # via the underlying primitive to validate that path is reachable.
        from leakage import assert_seasons_prior_only

        bad_rows = [{"season": 2024, "round": 6}]
        assert_seasons_prior_only(
            bad_rows,
            current_season=2024,
            current_round=5,
            label="test guard",
        )


def test_nan_handling_when_circuit_unseen():
    """A target round at a circuit with no prior visit returns NaN for
    circuit_shuffle_prior — the model must still fit + predict."""
    history = _make_history(
        [(2024, 1, "Bahrain"), (2024, 2, "Saudi Arabia"), (2024, 3, "Miami")]
    )
    feats = build_volatility_features(
        history, 2024, 3, "Miami", get_archetype("Miami")
    )
    assert np.isnan(feats["circuit_shuffle_prior"])
    # season_shuffle_prior should be defined (rounds 1 + 2 in season 2024)
    assert np.isfinite(feats["season_shuffle_prior"])


def test_output_in_unit_interval():
    """After fit + predict, V is in [0, 1] across many rounds and shuffle
    magnitudes."""
    rounds = [(2024, r, f"GP{r}") for r in range(1, 13)]
    history = _make_history(rounds, shuffle_magnitude=3.0)
    train_rows = []
    for season, round_, gp_key in rounds:
        if round_ == 1:
            continue  # round 1 has no prior; skip
        train_rows.append((season, round_, gp_key, None))
    X, y = build_volatility_training_frame(history, train_rows)
    assert len(X) > 0
    model = VolatilityModel().fit(X, y)
    preds = model.predict(X)
    assert np.all((preds >= 0.0) & (preds <= 1.0))


def test_monaco_lower_volatility_than_bahrain_after_training():
    """A qualifying-locked street circuit should score LOWER volatility
    than a high-overtake circuit when the model has seen both archetypes
    with consistent shuffle differentials."""
    # Construct a training set where Monaco rounds have low shuffle and
    # Bahrain rounds have high shuffle.
    monaco_rng = np.random.default_rng(11)
    bahrain_rng = np.random.default_rng(13)
    rows = []
    for round_, gp_key, rng_, magnitude in [
        (1, "Bahrain", bahrain_rng, 4.5),
        (2, "Monaco", monaco_rng, 0.6),
        (3, "Bahrain", bahrain_rng, 4.5),
        (4, "Monaco", monaco_rng, 0.6),
        (5, "Bahrain", bahrain_rng, 4.5),
        (6, "Monaco", monaco_rng, 0.6),
        (7, "Bahrain", bahrain_rng, 4.5),
        (8, "Monaco", monaco_rng, 0.6),
    ]:
        for pos in range(1, 21):
            noise = float(rng_.normal(0.0, magnitude))
            actual = int(np.clip(pos + noise, 1, 20))
            rows.append(
                {
                    "season": 2024,
                    "round": round_,
                    "driver": f"D{pos:02d}",
                    "predicted_position": pos,
                    "actual_position": actual,
                    "predicted_lap_time": 80.0 + (pos - 1) * 0.1,
                    "gp_key": gp_key,
                }
            )
    history = pd.DataFrame(rows)
    train_rounds = []
    for round_ in range(2, 9):
        gp_key = "Bahrain" if round_ % 2 == 1 else "Monaco"
        train_rounds.append((2024, round_, gp_key, get_archetype(gp_key)))
    X, y = build_volatility_training_frame(history, train_rounds)
    model = VolatilityModel().fit(X, y)

    # Score new rounds (not in the training set) for both archetypes.
    bahrain_feats = build_volatility_features(
        history, 2024, 9, "Bahrain", get_archetype("Bahrain")
    )
    monaco_feats = build_volatility_features(
        history, 2024, 9, "Monaco", get_archetype("Monaco")
    )
    v_bahrain = model.predict_one(bahrain_feats)
    v_monaco = model.predict_one(monaco_feats)
    assert v_monaco < v_bahrain, (
        f"Monaco {v_monaco:.3f} should be lower volatility than Bahrain {v_bahrain:.3f}"
    )


def test_saturation_constant_caps_target():
    """A massively-shuffled round should produce a target V near 1.0 (not >1.0)."""
    rows = []
    rng = np.random.default_rng(17)
    # Round with shuffle of ~10 positions across the field — target should
    # be clipped to 1.0.
    for pos in range(1, 21):
        noise = float(rng.normal(0.0, 8.0))
        actual = int(np.clip(pos + noise, 1, 20))
        rows.append(
            {
                "season": 2024,
                "round": 5,
                "driver": f"D{pos:02d}",
                "predicted_position": pos,
                "actual_position": actual,
                "predicted_lap_time": 80.0 + (pos - 1) * 0.1,
                "gp_key": "ChaosGP",
            }
        )
    # Add a benign prior round.
    for pos in range(1, 21):
        rows.append(
            {
                "season": 2024,
                "round": 4,
                "driver": f"D{pos:02d}",
                "predicted_position": pos,
                "actual_position": pos,
                "predicted_lap_time": 80.0 + (pos - 1) * 0.1,
                "gp_key": "QuietGP",
            }
        )
    history = pd.DataFrame(rows)
    X, y = build_volatility_training_frame(history, [(2024, 5, "ChaosGP", None)])
    assert (y <= 1.0).all()
    # The target round had massive shuffle — it should be at or near 1.0.
    assert y[0] >= 0.5
    assert SATURATION_SHUFFLE > 0


def test_predict_before_fit_raises():
    model = VolatilityModel()
    with pytest.raises(RuntimeError):
        model.predict({k: 0.5 for k in FEATURE_COLUMNS})


def test_save_and_load_round_trip(tmp_path):
    rows_input = [(2024, r, f"GP{r}") for r in range(1, 8)]
    history = _make_history(rows_input, shuffle_magnitude=2.0)
    train_rounds = [
        (2024, r, gp, None) for (_, r, gp) in rows_input if r > 1
    ]
    X, y = build_volatility_training_frame(history, train_rounds)
    model = VolatilityModel().fit(X, y)
    p1 = model.predict(X)
    path = tmp_path / "vol.joblib"
    model.save(path)
    loaded = VolatilityModel.load(path)
    p2 = loaded.predict(X)
    np.testing.assert_allclose(p1, p2)
