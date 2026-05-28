"""Tests for the weekend-feature loader."""
from __future__ import annotations

import pandas as pd
import pytest

from models.weekend_features import (
    WEEKEND_FEATURE_COLUMNS,
    attach_weekend_to_history,
    clear_cache,
    get_weekend_features,
)


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """Use a fresh in-memory cache per test."""
    clear_cache()
    yield
    clear_cache()


def _make_parquet(tmp_path, rows: list[dict]) -> str:
    out = tmp_path / "weekend.parquet"
    pd.DataFrame(rows).to_parquet(out, index=False)
    return out


def test_get_weekend_features_returns_one_row_per_driver(tmp_path):
    p = _make_parquet(
        tmp_path,
        [
            dict(season=2024, round=1, driver="VER", fp2_longrun_pace_norm=1.00,
                 fp2_longrun_consistency=0.10, q_sector_dominance_norm=1.00,
                 q_top_speed_norm=1.00, race_track_temp=22.0, race_air_temp=18.0,
                 race_rainfall=0.0, fp2_deg_slope=0.05,
                 q_vs_fp2_pace_delta=-0.01, intra_stint_drift=0.2),
            dict(season=2024, round=1, driver="HAM", fp2_longrun_pace_norm=1.02,
                 fp2_longrun_consistency=0.12, q_sector_dominance_norm=1.01,
                 q_top_speed_norm=0.99, race_track_temp=22.0, race_air_temp=18.0,
                 race_rainfall=0.0, fp2_deg_slope=0.06,
                 q_vs_fp2_pace_delta=-0.005, intra_stint_drift=0.3),
        ],
    )
    out = get_weekend_features(2024, 1, ["HAM", "VER", "ALB"], path=p)
    assert list(out["driver"]) == ["HAM", "VER", "ALB"]
    # ALB has no coverage → all weekend columns are NaN
    for col in WEEKEND_FEATURE_COLUMNS:
        assert pd.isna(out.loc[out["driver"] == "ALB", col].iloc[0])
    # VER fp2_pace is 1.0 (fastest)
    assert float(out.loc[out["driver"] == "VER", "fp2_longrun_pace_norm"].iloc[0]) == 1.00


def test_get_weekend_features_missing_round_returns_nan(tmp_path):
    p = _make_parquet(
        tmp_path,
        [dict(season=2024, round=1, driver="VER", fp2_longrun_pace_norm=1.0,
              fp2_longrun_consistency=0.1, q_sector_dominance_norm=1.0,
              q_top_speed_norm=1.0, race_track_temp=22.0, race_air_temp=18.0,
              race_rainfall=0.0, fp2_deg_slope=0.05,
              q_vs_fp2_pace_delta=-0.01, intra_stint_drift=0.2)],
    )
    # Ask for round 5 — not in the parquet
    out = get_weekend_features(2024, 5, ["VER"], path=p)
    assert len(out) == 1
    for col in WEEKEND_FEATURE_COLUMNS:
        assert pd.isna(out[col].iloc[0])


def test_get_weekend_features_no_parquet_returns_all_nan(tmp_path):
    missing = tmp_path / "does_not_exist.parquet"
    out = get_weekend_features(2024, 1, ["VER", "HAM"], path=missing)
    assert len(out) == 2
    for col in WEEKEND_FEATURE_COLUMNS:
        assert out[col].isna().all()


def test_attach_weekend_to_history_left_joins(tmp_path):
    p = _make_parquet(
        tmp_path,
        [dict(season=2024, round=1, driver="VER", fp2_longrun_pace_norm=1.0,
              fp2_longrun_consistency=0.1, q_sector_dominance_norm=1.0,
              q_top_speed_norm=1.0, race_track_temp=22.0, race_air_temp=18.0,
              race_rainfall=0.0, fp2_deg_slope=0.05,
              q_vs_fp2_pace_delta=-0.01, intra_stint_drift=0.2)],
    )
    history = pd.DataFrame(
        [
            dict(season=2024, round=1, driver="VER", actual_position=1),
            dict(season=2024, round=2, driver="VER", actual_position=2),
        ]
    )
    out = attach_weekend_to_history(history, path=p)
    assert len(out) == 2
    assert float(out.iloc[0]["fp2_longrun_pace_norm"]) == 1.0
    assert pd.isna(out.iloc[1]["fp2_longrun_pace_norm"])


def test_weekend_feature_columns_constant_consistent() -> None:
    # After the Phase 10 freeze, WEEKEND_FEATURE_COLUMNS is the canonical
    # 7-column production set. The 3 Phase-8 dynamic curves are archived to
    # ARCHIVED_DYNAMIC_COLUMNS and are NOT in the production tuple.
    from models.weekend_features import (
        ARCHIVED_DYNAMIC_COLUMNS,
        WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH,
    )
    assert len(WEEKEND_FEATURE_COLUMNS) == 7
    assert "fp2_longrun_pace_norm" in WEEKEND_FEATURE_COLUMNS
    assert "race_rainfall" in WEEKEND_FEATURE_COLUMNS
    # Archived columns must NOT be in the production set.
    for archived in ARCHIVED_DYNAMIC_COLUMNS:
        assert archived not in WEEKEND_FEATURE_COLUMNS, (
            f"archived column {archived!r} must not be in production set"
        )
    # Research alias is still the full 10-column set.
    assert len(WEEKEND_FEATURE_COLUMNS_WITH_RESEARCH) == 10
