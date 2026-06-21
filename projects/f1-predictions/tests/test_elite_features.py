"""Tests for models.elite_features.

Focus areas:
  1. Leakage discipline — features for (S, R) must be unchanged whether
     or not rows for (S, R+) exist in the input.
  2. Strict prior-only — for both season-level and historical-level
     aggregations.
  3. Feature semantics — qualifying_dominance direction, NaN sentinels.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from leakage import LeakageError
from models.elite_features import (
    FEATURE_COLUMNS,
    build_elite_features,
    build_elite_features_batch,
)


def _make_round_rows(
    season: int,
    round_: int,
    drivers: list[str],
    actual_positions: list[int] | None,
    lap_times: list[float] | None = None,
) -> list[dict]:
    """Helper: synth a small per-round frame in DB shape."""
    n = len(drivers)
    if lap_times is None:
        lap_times = [80.0 + i * 0.2 for i in range(n)]
    if actual_positions is None:
        actual_positions = [None] * n
    rows = []
    for i, drv in enumerate(drivers):
        rows.append(
            {
                "season": season,
                "round": round_,
                "driver": drv,
                "predicted_position": i + 1,
                "actual_position": actual_positions[i]
                if actual_positions[i] is not None
                else float("nan"),
                "predicted_lap_time": lap_times[i],
            }
        )
    return rows


@pytest.fixture
def base_history() -> pd.DataFrame:
    """5 prior rounds + a target round (2024, R5). Two seasons in the mix."""
    rows: list[dict] = []
    drivers = ["VER", "NOR", "PIA", "HAM", "RUS", "LEC"]
    # 2023 R1-R3, varying podiums
    rows.extend(
        _make_round_rows(2023, 1, drivers, [1, 4, 5, 2, 3, 6])  # VER P1, RUS P3
    )
    rows.extend(
        _make_round_rows(2023, 2, drivers, [1, 2, 3, 4, 5, 6])  # VER/NOR/PIA podium
    )
    rows.extend(
        _make_round_rows(2023, 3, drivers, [2, 1, 4, 3, 5, 6])  # NOR/VER/HAM
    )
    # 2024 R1-R4 prior to target
    rows.extend(
        _make_round_rows(2024, 1, drivers, [1, 2, 4, 5, 3, 6])  # VER/NOR/RUS
    )
    rows.extend(
        _make_round_rows(2024, 2, drivers, [3, 1, 2, 6, 4, 5])  # NOR/PIA/VER
    )
    rows.extend(
        _make_round_rows(2024, 3, drivers, [1, 2, 3, 4, 5, 6])  # VER/NOR/PIA
    )
    rows.extend(
        _make_round_rows(2024, 4, drivers, [2, 1, 3, 5, 4, 6])  # NOR/VER/PIA
    )
    # Target (no actuals yet — this is the prediction round)
    rows.extend(
        _make_round_rows(2024, 5, drivers, [None, None, None, None, None, None])
    )
    return pd.DataFrame(rows)


def test_features_returned_for_each_driver(base_history):
    feats = build_elite_features(base_history, target_season=2024, target_round=5)
    assert len(feats) == 6
    assert set(feats["driver"]) == {"VER", "NOR", "PIA", "HAM", "RUS", "LEC"}
    for col in FEATURE_COLUMNS:
        assert col in feats.columns, f"missing feature column {col}"


def test_no_leakage_when_future_rows_present(base_history):
    """Adding (2024, R5+) rows to the input must NOT change features for R5."""
    feats_clean = build_elite_features(base_history, 2024, 5).set_index("driver")
    # Tack on a "future" round with actuals — should be silently ignored.
    future = pd.DataFrame(
        _make_round_rows(
            2024, 6, ["VER", "NOR", "PIA", "HAM", "RUS", "LEC"],
            [1, 2, 3, 4, 5, 6],
        )
    )
    leaky_input = pd.concat([base_history, future], ignore_index=True)
    feats_leaky = build_elite_features(leaky_input, 2024, 5).set_index("driver")

    # Every feature column must match exactly (NaN-aware).
    for col in FEATURE_COLUMNS:
        clean = feats_clean[col].fillna(-999).to_numpy()
        leaky = feats_leaky[col].fillna(-999).to_numpy()
        np.testing.assert_allclose(
            clean, leaky, err_msg=f"feature {col} changed when future rows added"
        )


def test_no_leakage_when_target_round_actuals_present(base_history):
    """Even if the target round has actuals (post-race rerun), the features
    must not aggregate over the target round itself."""
    with_actuals = base_history.copy()
    mask = (with_actuals["season"] == 2024) & (with_actuals["round"] == 5)
    with_actuals.loc[mask, "actual_position"] = [1, 2, 3, 4, 5, 6]

    feats_without = build_elite_features(base_history, 2024, 5).set_index("driver")
    feats_with = build_elite_features(with_actuals, 2024, 5).set_index("driver")

    for col in FEATURE_COLUMNS:
        a = feats_without[col].fillna(-999).to_numpy()
        b = feats_with[col].fillna(-999).to_numpy()
        np.testing.assert_allclose(
            a, b, err_msg=f"feature {col} changed when target actuals present"
        )


def test_season_features_are_strictly_prior(base_history):
    """driver_podium_rate_season for (2024, R5) must only count R1-R4."""
    feats = build_elite_features(base_history, 2024, 5).set_index("driver")
    # VER actuals in 2024 prior rounds: R1=1, R2=3, R3=1, R4=2 → 4 podiums in 4
    assert math.isclose(feats.loc["VER", "driver_podium_rate_season"], 1.0)
    # VER winner rate season: R1=1, R3=1 → 2/4 = 0.5
    assert math.isclose(feats.loc["VER", "driver_winner_rate_season"], 0.5)
    # HAM 2024 finishes: R1=5, R2=6, R3=4, R4=5 — no podiums
    assert math.isclose(feats.loc["HAM", "driver_podium_rate_season"], 0.0)


def test_recent_window_uses_last_5_across_seasons(base_history):
    """driver_podium_rate_5 should pool across seasons."""
    feats = build_elite_features(base_history, 2024, 5).set_index("driver")
    # VER last 5 actuals (chronological, prior-only): 2023 R1=1, R2=1, R3=2,
    # 2024 R1=1, R2=3, R3=1, R4=2 → tail-5 = [R3-2023, R1-2024, R2-2024, R3-2024, R4-2024]
    # = [2, 1, 3, 1, 2] → 5 podiums out of 5 → 1.0
    assert math.isclose(feats.loc["VER", "driver_podium_rate_5"], 1.0)


def test_circuit_podium_rate_needs_min_visits(base_history):
    """With only one prior visit at the same circuit, return NaN."""
    # (2024, R5) maps to gp_key 'China' under the live map. None of the
    # prior rounds in the fixture share that key — so circuit_podium_rate
    # should be NaN for every driver.
    feats = build_elite_features(base_history, 2024, 5).set_index("driver")
    for drv in feats.index:
        assert math.isnan(feats.loc[drv, "driver_circuit_podium_rate"]), (
            f"{drv} expected NaN circuit rate (no prior visits)"
        )


def test_qualifying_dominance_direction():
    """The pole-sitter gets 0; every slower driver gets gap to next-fastest."""
    rows = []
    rows.extend(
        _make_round_rows(2023, 1, ["A", "B", "C"], [1, 2, 3])
    )
    rows.extend(
        _make_round_rows(2023, 2, ["A", "B", "C"], [1, 2, 3])
    )
    rows.extend(
        _make_round_rows(2023, 3, ["A", "B", "C"], [1, 2, 3])
    )
    # Target round with specific lap-time gaps
    rows.extend(
        _make_round_rows(
            2024, 1, ["A", "B", "C"],
            actual_positions=[None, None, None],
            lap_times=[80.0, 80.5, 81.2],
        )
    )
    history = pd.DataFrame(rows)
    feats = build_elite_features(history, 2024, 1).set_index("driver")
    # A is pole → 0.0
    assert math.isclose(feats.loc["A", "qualifying_dominance"], 0.0)
    # B's gap to A is 0.5
    assert math.isclose(feats.loc["B", "qualifying_dominance"], 0.5, abs_tol=1e-9)
    # C's gap to B is 0.7
    assert math.isclose(feats.loc["C", "qualifying_dominance"], 0.7, abs_tol=1e-9)


def test_nan_when_no_prior_data():
    """First race of recorded history: all driver-history features should be NaN."""
    drivers = ["A", "B", "C"]
    history = pd.DataFrame(
        _make_round_rows(2024, 1, drivers, [None, None, None])
    )
    feats = build_elite_features(history, 2024, 1).set_index("driver")
    for drv in drivers:
        for col in (
            "driver_podium_rate_5",
            "driver_podium_rate_season",
            "driver_winner_rate_season",
            "driver_circuit_podium_rate",
        ):
            assert math.isnan(feats.loc[drv, col]), (
                f"{drv}.{col} expected NaN with no prior data"
            )
        # qualifying_dominance still resolves from the current round's lap times.
        assert not math.isnan(feats.loc[drv, "qualifying_dominance"])


def test_leakage_assertion_raised_when_prior_includes_target():
    """Direct test of the internal boundary check — build a degenerate
    history_df where assert_seasons_prior_only would fire."""
    # build_elite_features calls assert_seasons_prior_only on its prior
    # frame. We can't trip it via the public API (the function itself
    # filters first), so verify the assertion module catches it.
    from leakage import assert_seasons_prior_only

    rows = [
        {"season": 2024, "round": 6, "driver": "X"},
        {"season": 2024, "round": 7, "driver": "Y"},
    ]
    with pytest.raises(LeakageError):
        assert_seasons_prior_only(rows, current_season=2024, current_round=5)


def test_batch_builder_concatenates_rounds(base_history):
    out = build_elite_features_batch(
        base_history, target_rounds=[(2024, 4), (2024, 5)]
    )
    assert {(s, r) for s, r in zip(out["season"], out["round"])} == {
        (2024, 4), (2024, 5)
    }
    # Same driver, two rounds → 12 rows for 6 drivers
    assert len(out) == 12
