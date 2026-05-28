"""Tests for models.conversion_model."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from leakage import LeakageError, assert_seasons_prior_only
from models.conversion_model import (
    FEATURE_COLUMNS,
    ConversionPodiumHead,
    ConversionWinHead,
    build_conversion_features,
)


def _make_history(n_rounds: int = 8, drivers: int = 20, seed: int = 42) -> pd.DataFrame:
    """History where driver A is the dominant elite (wins when predicted P1,
    podiums when predicted top-3) and the rest of the field is noisier."""
    rng = np.random.default_rng(seed)
    rows = []
    for rnd in range(1, n_rounds + 1):
        for slot in range(drivers):
            drv = "A" if slot == 0 else ("B" if slot == 1 else f"D{slot:02d}")
            pred = slot + 1
            if drv == "A":
                # A converts predictions consistently.
                actual = pred if pred <= 3 else int(np.clip(pred + rng.integers(-1, 2), 1, drivers))
            elif drv == "B":
                # B converts well but not perfectly.
                actual = int(np.clip(pred + rng.integers(-1, 3), 1, drivers))
            else:
                actual = int(np.clip(pred + rng.integers(-3, 4), 1, drivers))
            rows.append(
                {
                    "season": 2024,
                    "round": rnd,
                    "driver": drv,
                    "predicted_position": pred,
                    "actual_position": actual,
                    "predicted_lap_time": 80.0 + (pred - 1) * 0.15,
                    "gp_key": f"GP{rnd}",
                }
            )
    return pd.DataFrame(rows)


def test_build_features_columns_present():
    history = _make_history()
    feats = build_conversion_features(history, 2024, 5, "GP5")
    for col in FEATURE_COLUMNS:
        assert col in feats.columns
    # One row per driver in target round.
    assert len(feats) == int(history[(history.season == 2024) & (history["round"] == 5)].shape[0])


def test_leak_protection_assertion():
    """The leakage assertion fires when a row >= target sneaks in."""
    with pytest.raises(LeakageError):
        assert_seasons_prior_only(
            [{"season": 2024, "round": 5}],
            current_season=2024,
            current_round=5,
            label="conversion guard",
        )


def test_features_use_only_prior_data():
    """A feature value built at round R must not change if you ADD a round R+1."""
    history_8 = _make_history(n_rounds=8)
    feats_at_5 = build_conversion_features(history_8, 2024, 5, "GP5")
    # Truncate history to rounds <= 8 (already), no change. Now build the SAME
    # query against a history that includes 'future' rounds — the feature
    # builder should filter them out.
    history_20 = pd.concat([history_8, _make_history(n_rounds=20)[
        _make_history(n_rounds=20)["round"] > 8
    ]], ignore_index=True)
    feats_at_5_b = build_conversion_features(history_20, 2024, 5, "GP5")
    # The conversion features should be identical (the function strips
    # at-or-after rows before aggregating).
    pd.testing.assert_frame_equal(
        feats_at_5.sort_values("driver").reset_index(drop=True)[list(FEATURE_COLUMNS)],
        feats_at_5_b.sort_values("driver").reset_index(drop=True)[list(FEATURE_COLUMNS)],
    )


def test_nan_sentinels_for_unseen_circuit():
    """A first-visit circuit yields NaN for driver_circuit_conversion."""
    history = _make_history(n_rounds=4)
    # GP5 has never been visited; circuit conversion should be NaN for all.
    feats = build_conversion_features(history, 2024, 5, "BrandNewCircuit")
    # But the target round (2024, 5) isn't in history. Add one driver-row so
    # we have a target frame.
    history = pd.concat(
        [
            history,
            pd.DataFrame(
                [
                    {
                        "season": 2024,
                        "round": 5,
                        "driver": "A",
                        "predicted_position": 1,
                        "actual_position": np.nan,
                        "predicted_lap_time": 80.0,
                        "gp_key": "BrandNewCircuit",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    feats = build_conversion_features(history, 2024, 5, "BrandNewCircuit")
    assert "driver_circuit_conversion" in feats.columns
    assert np.isnan(feats.iloc[0]["driver_circuit_conversion"])


def test_p_win_sums_sensibly_across_field():
    """Per-round mean P(win) should be in a sane band — not collapsed to 0
    or 1 across the field."""
    history = _make_history(n_rounds=12, drivers=20)
    feats_5 = build_conversion_features(history, 2024, 5, "GP5")
    history["target_y"] = history["actual_position"]
    # Train on rounds 2..4 (round 1 has no prior).
    train_feats_parts = []
    for rnd in [2, 3, 4]:
        f = build_conversion_features(history, 2024, rnd, f"GP{rnd}")
        f = f.merge(
            history[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        train_feats_parts.append(f)
    train_full = pd.concat(train_feats_parts, ignore_index=True)
    train_full = train_full[train_full["actual_position"].notna()].reset_index(drop=True)
    head = ConversionWinHead().fit(train_full, train_full["actual_position"])
    probs = head.predict_proba(feats_5)
    # Expect: mean P(win) across the field should be in [0.005, 0.5] —
    # loose band to catch obvious breakage.
    assert 0.005 <= float(np.mean(probs)) <= 0.5


def test_head_learns_signal_on_constructed_example():
    """Driver A (the dominant elite) should score higher P(podium) than the field."""
    history = _make_history(n_rounds=10, drivers=20)
    feats_parts = []
    for rnd in range(2, 10):
        f = build_conversion_features(history, 2024, rnd, f"GP{rnd}")
        f = f.merge(
            history[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        feats_parts.append(f)
    train_full = pd.concat(feats_parts, ignore_index=True)
    train_full = train_full[train_full["actual_position"].notna()].reset_index(drop=True)
    head = ConversionPodiumHead().fit(train_full, train_full["actual_position"])
    target_feats = build_conversion_features(history, 2024, 10, "GP10")
    probs = head.predict_proba(target_feats)
    target_feats = target_feats.copy()
    target_feats["prob"] = probs
    a_prob = float(target_feats[target_feats["driver"] == "A"]["prob"].iloc[0])
    field_prob = float(
        target_feats[~target_feats["driver"].isin(["A", "B"])]["prob"].mean()
    )
    assert a_prob > field_prob, (
        f"A's prob {a_prob:.3f} should beat field mean {field_prob:.3f}"
    )


def test_no_current_round_contamination_in_features():
    """The driver-history aggregates must NOT include the target-round row."""
    history = _make_history(n_rounds=8)
    feats = build_conversion_features(history, 2024, 4, "GP4")
    # The driver_podium_given_top3 for round 4 must be computed using rounds
    # 1..3 only. Verify by re-building with rounds 1..3 only and comparing.
    history_truncated = history[history["round"] < 4].copy()
    # Need to inject a synthetic round-4 frame so the builder has a target
    # frame to iterate.
    target_frame = history[history["round"] == 4].copy()
    history_truncated = pd.concat([history_truncated, target_frame], ignore_index=True)
    feats_truncated = build_conversion_features(history_truncated, 2024, 4, "GP4")
    pd.testing.assert_frame_equal(
        feats.sort_values("driver").reset_index(drop=True)[list(FEATURE_COLUMNS)],
        feats_truncated.sort_values("driver").reset_index(drop=True)[list(FEATURE_COLUMNS)],
    )


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        ConversionPodiumHead().predict_proba(pd.DataFrame(columns=FEATURE_COLUMNS))


def test_save_load_round_trip(tmp_path):
    history = _make_history(n_rounds=10)
    feats_parts = []
    for rnd in range(2, 10):
        f = build_conversion_features(history, 2024, rnd, f"GP{rnd}")
        f = f.merge(
            history[["season", "round", "driver", "actual_position"]],
            on=["season", "round", "driver"],
            how="left",
        )
        feats_parts.append(f)
    train_full = pd.concat(feats_parts, ignore_index=True)
    train_full = train_full[train_full["actual_position"].notna()].reset_index(drop=True)
    head = ConversionPodiumHead().fit(train_full, train_full["actual_position"])
    target = build_conversion_features(history, 2024, 10, "GP10")
    p1 = head.predict_proba(target)
    path = tmp_path / "podium.joblib"
    head.save(path)
    loaded = ConversionPodiumHead.load(path)
    p2 = loaded.predict_proba(target)
    np.testing.assert_allclose(p1, p2)
