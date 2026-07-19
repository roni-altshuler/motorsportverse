"""Tests for the per-lap race-pace regression model.

FastF1 is monkeypatched at ``models.race_pace._load_race_session``; no test
hits the network.  We construct synthetic FastF1-shaped DataFrames that
mirror the real schema closely enough to exercise the feature engineering
and training paths.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from models import race_pace
from models.race_pace import (
    COMPOUND_CODES,
    FEATURE_COLUMNS,
    LEADER_GAP_SENTINEL_S,
    TARGET_COLUMN,
    LapRecord,
    build_training_dataset,
    laps_to_features,
    load_race_laps,
    predict_lap_times,
    train_race_pace_model,
    transform_features,
)


# --------------------------------------------------------------------------- #
# Synthetic data helpers
# --------------------------------------------------------------------------- #


def _make_lap(
    *,
    driver: str = "VER",
    team: str = "RED BULL",
    circuit_key: str = "Monaco",
    lap_number: int = 1,
    track_position: int = 1,
    lap_time_s: float = 80.0,
    tyre_compound: str = "SOFT",
    tyre_age_laps: int = 1,
    gap_ahead: float | None = None,
    gap_behind: float | None = 1.5,
    sc_active: bool = False,
    vsc_active: bool = False,
    yellow_active: bool = False,
    air_temp_c: float | None = 25.0,
    track_temp_c: float | None = 35.0,
    rain_intensity: float | None = 0.0,
    total_laps: int = 78,
) -> LapRecord:
    return LapRecord(
        season=2024,
        round=8,
        circuit_key=circuit_key,
        driver=driver,
        team=team,
        lap_number=lap_number,
        lap_time_s=lap_time_s,
        total_laps=total_laps,
        track_position=track_position,
        tyre_compound=tyre_compound,
        tyre_age_laps=tyre_age_laps,
        sc_active=sc_active,
        vsc_active=vsc_active,
        yellow_active=yellow_active,
        gap_to_car_ahead_s=gap_ahead,
        gap_to_car_behind_s=gap_behind,
        air_temp_c=air_temp_c,
        track_temp_c=track_temp_c,
        rain_intensity=rain_intensity,
    )


def _synthetic_laps_dataframe(n_drivers: int = 6, n_laps: int = 12) -> pd.DataFrame:
    """A FastF1-shaped ``laps`` DataFrame with the columns ``_lap_row_to_record``
    actually reads."""
    rows: list[dict[str, Any]] = []
    drivers = [f"D{i:02d}" for i in range(n_drivers)]
    teams = [f"T{i:02d}" for i in range(n_drivers)]
    for lap_num in range(1, n_laps + 1):
        # Deterministic per-driver pace: D00 is fastest, monotonic in driver idx.
        base = 80.0 + 0.5 * (lap_num - 1) * 0.0  # constant base time
        for i, drv in enumerate(drivers):
            lap_time = base + 0.15 * i + 0.04 * (lap_num - 1)
            cumulative_time = lap_time * lap_num + 0.15 * i
            rows.append(
                {
                    "Driver": drv,
                    "Team": teams[i],
                    "LapNumber": lap_num,
                    "LapTime": pd.Timedelta(seconds=lap_time),
                    "Compound": "MEDIUM" if lap_num <= 7 else "HARD",
                    "TyreLife": lap_num if lap_num <= 7 else lap_num - 7,
                    "TrackStatus": "1",
                    "Position": i + 1,
                    "Time": pd.Timedelta(seconds=cumulative_time),
                }
            )
    return pd.DataFrame(rows)


def _synthetic_weather_dataframe(n_samples: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Time": [pd.Timedelta(seconds=80 * i) for i in range(1, n_samples + 1)],
            "AirTemp": [24.0 + 0.1 * i for i in range(n_samples)],
            "TrackTemp": [34.0 + 0.2 * i for i in range(n_samples)],
            "Rainfall": [False] * n_samples,
        }
    )


# --------------------------------------------------------------------------- #
# FastF1 loader integration (mocked)
# --------------------------------------------------------------------------- #


class TestLoadRaceLaps:
    def test_returns_records_from_synthetic_session(self, monkeypatch: pytest.MonkeyPatch):
        laps_df = _synthetic_laps_dataframe(n_drivers=4, n_laps=5)
        weather_df = _synthetic_weather_dataframe(5)

        def fake_load(season: int, round_num: int):  # noqa: ARG001
            return SimpleNamespace(
                laps=laps_df, weather_data=weather_df, event={"Location": "Test Circuit"}
            )

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        records = load_race_laps(2024, 8, circuit_key="Test")
        # 4 drivers × 5 laps = 20 LapRecords
        assert len(records) == 20
        assert all(isinstance(r, LapRecord) for r in records)
        # All laps should have circuit_key='Test', season=2024, round=8
        assert {r.circuit_key for r in records} == {"Test"}
        assert {r.season for r in records} == {2024}

    def test_returns_empty_on_load_failure(self, monkeypatch: pytest.MonkeyPatch):
        def fake_load(season: int, round_num: int):  # noqa: ARG001
            raise RuntimeError("simulated FastF1 timeout")

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        with pytest.warns(UserWarning, match="session load failed"):
            assert load_race_laps(2024, 8, circuit_key="Test") == []

    def test_skips_rows_with_no_lap_time(self, monkeypatch: pytest.MonkeyPatch):
        laps_df = _synthetic_laps_dataframe(n_drivers=2, n_laps=3)
        # Wipe one lap-time → that row must be filtered out
        laps_df.loc[laps_df.index[1], "LapTime"] = pd.NaT

        def fake_load(season: int, round_num: int):  # noqa: ARG001
            return SimpleNamespace(laps=laps_df, weather_data=None, event={"Location": "X"})

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        records = load_race_laps(2024, 8, circuit_key="X")
        # 2 drivers × 3 laps = 6 expected; one wiped = 5
        assert len(records) == 5

    def test_track_status_flags_decoded(self, monkeypatch: pytest.MonkeyPatch):
        laps_df = _synthetic_laps_dataframe(n_drivers=1, n_laps=4)
        laps_df.loc[laps_df.index[0], "TrackStatus"] = "1"        # green
        laps_df.loc[laps_df.index[1], "TrackStatus"] = "2"        # yellow
        laps_df.loc[laps_df.index[2], "TrackStatus"] = "4"        # SC
        laps_df.loc[laps_df.index[3], "TrackStatus"] = "67"       # VSC + VSC-ending

        def fake_load(season: int, round_num: int):  # noqa: ARG001
            return SimpleNamespace(laps=laps_df, weather_data=None, event={"Location": "X"})

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        records = load_race_laps(2024, 8, circuit_key="X")
        assert records[0].sc_active is False
        assert records[1].yellow_active is True
        assert records[2].sc_active is True
        assert records[3].vsc_active is True

    def test_gaps_computed_from_position_and_time(self, monkeypatch: pytest.MonkeyPatch):
        laps_df = _synthetic_laps_dataframe(n_drivers=3, n_laps=2)

        def fake_load(season: int, round_num: int):  # noqa: ARG001
            return SimpleNamespace(laps=laps_df, weather_data=None, event={"Location": "X"})

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        records = load_race_laps(2024, 8, circuit_key="X")
        # Leader (Position=1) → gap_to_car_ahead_s is None
        leader = [r for r in records if r.track_position == 1][0]
        assert leader.gap_to_car_ahead_s is None
        # Non-leaders have a positive gap to the car ahead
        followers = [r for r in records if r.track_position > 1]
        assert all(
            r.gap_to_car_ahead_s is not None and r.gap_to_car_ahead_s >= 0
            for r in followers
        )

    def test_unknown_compound_normalised(self, monkeypatch: pytest.MonkeyPatch):
        laps_df = _synthetic_laps_dataframe(n_drivers=1, n_laps=1)
        laps_df.loc[laps_df.index[0], "Compound"] = "MYSTERY"

        def fake_load(season: int, round_num: int):  # noqa: ARG001
            return SimpleNamespace(laps=laps_df, weather_data=None, event={"Location": "X"})

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        records = load_race_laps(2024, 8, circuit_key="X")
        assert records[0].tyre_compound == "UNKNOWN"

    def test_handles_pandas_event_series_without_truthiness_crash(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Regression: FastF1 returns ``session.event`` as a pandas Series
        which raises on ``event or {}``.  Caller must accept either shape."""
        laps_df = _synthetic_laps_dataframe(n_drivers=2, n_laps=2)
        # Simulate FastF1's pandas-Series event
        event_series = pd.Series({"Location": "FakeCircuitFromSeries", "EventName": "X"})

        def fake_load(season: int, round_num: int):  # noqa: ARG001
            return SimpleNamespace(
                laps=laps_df, weather_data=None, event=event_series,
            )

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        records = load_race_laps(2024, 8)  # no circuit_key → derived from event
        assert records, "loader should not crash on a pandas-Series event"
        assert records[0].circuit_key == "FakeCircuitFromSeries"


# --------------------------------------------------------------------------- #
# Feature engineering
# --------------------------------------------------------------------------- #


class TestLapsToFeatures:
    def test_returns_empty_df_for_empty_input(self):
        df, encoders = laps_to_features([])
        assert df.empty
        # All expected columns present (target + features)
        for col in [*FEATURE_COLUMNS, TARGET_COLUMN]:
            assert col in df.columns

    def test_label_encoders_assign_stable_ids(self):
        laps = [
            _make_lap(driver="VER", team="RED BULL", circuit_key="Monaco"),
            _make_lap(driver="NOR", team="MCLAREN", circuit_key="Monaco"),
            _make_lap(driver="VER", team="RED BULL", circuit_key="Monaco", lap_number=2),
        ]
        df, encoders = laps_to_features(laps)
        # VER appears twice with the same id; NOR has a different id
        ver_ids = df[df["lap_number"].between(1, 2)]["driver_id"].unique().tolist()
        assert len(ver_ids) == 2  # VER and NOR are distinct codes
        assert encoders["driver"]["VER"] == 0
        assert encoders["driver"]["NOR"] == 1

    def test_leader_gap_replaced_with_sentinel(self):
        lap = _make_lap(gap_ahead=None, gap_behind=2.0)
        df, _ = laps_to_features([lap])
        assert df.iloc[0]["gap_to_car_ahead_s"] == LEADER_GAP_SENTINEL_S
        assert df.iloc[0]["gap_to_car_behind_s"] == 2.0

    def test_weather_defaults_when_missing(self):
        lap = _make_lap(air_temp_c=None, track_temp_c=None, rain_intensity=None)
        df, _ = laps_to_features([lap])
        # Sensible dry-weather defaults so the model isn't fed NaNs
        assert df.iloc[0]["air_temp_c"] == 25.0
        assert df.iloc[0]["track_temp_c"] == 35.0
        assert df.iloc[0]["rain_intensity"] == 0.0

    def test_compound_codes_match_lookup(self):
        for compound, code in COMPOUND_CODES.items():
            lap = _make_lap(tyre_compound=compound)
            df, _ = laps_to_features([lap])
            assert int(df.iloc[0]["tyre_compound_code"]) == code

    def test_lap_progress_normalised(self):
        lap_mid = _make_lap(lap_number=39, total_laps=78)
        df, _ = laps_to_features([lap_mid])
        assert df.iloc[0]["lap_progress"] == pytest.approx(0.5)


class TestTransformFeatures:
    def test_unknown_categorical_maps_to_minus_one(self):
        # Build an encoder from a known driver set, then transform an unknown driver.
        known = [_make_lap(driver="VER"), _make_lap(driver="NOR")]
        _, encoders = laps_to_features(known)
        unknown_lap = _make_lap(driver="UNK", team="ALIEN")
        df = transform_features([unknown_lap], encoders)
        assert df.iloc[0]["driver_id"] == -1
        assert df.iloc[0]["team_id"] == -1

    def test_frozen_encoder_does_not_grow(self):
        known = [_make_lap(driver="VER")]
        _, encoders = laps_to_features(known)
        before = dict(encoders["driver"])
        transform_features([_make_lap(driver="NEW")], encoders)
        # Frozen-at-inference: the encoder mapping passed in must not grow
        assert dict(encoders["driver"]) == before


# --------------------------------------------------------------------------- #
# Training + inference
# --------------------------------------------------------------------------- #


def _training_set(n: int = 60) -> pd.DataFrame:
    """A small but learnable synthetic dataset.

    Target is a near-linear function of a few features, with mild noise, so
    GBR + XGB can recover it well enough to validate the training path.
    """
    rng = np.random.default_rng(seed=0)
    laps: list[LapRecord] = []
    for i in range(n):
        driver = f"D{i % 5:02d}"
        team = f"T{i % 3:02d}"
        compound = ["SOFT", "MEDIUM", "HARD"][i % 3]
        position = (i % 10) + 1
        tyre_age = i % 20
        # Target ~ base + driver_offset + position_penalty + tyre_age_drag
        base = 80.0
        target = base + 0.15 * (i % 5) + 0.05 * position + 0.02 * tyre_age + rng.normal(0, 0.05)
        laps.append(
            replace(
                _make_lap(
                    driver=driver,
                    team=team,
                    lap_number=(i % 12) + 1,
                    track_position=position,
                    tyre_compound=compound,
                    tyre_age_laps=tyre_age,
                    gap_ahead=None if position == 1 else 1.0 + 0.5 * position,
                    gap_behind=1.0 + 0.5 * position,
                    lap_time_s=float(target),
                )
            )
        )
    df, _ = laps_to_features(laps)
    return df


class TestTrainRacePaceModel:
    def test_train_returns_registry_compatible_artifacts(self):
        df = _training_set(n=80)
        art = train_race_pace_model(df, test_size=0.25)
        assert "gbr" in art
        assert "xgb" in art
        assert art["feature_columns"] == list(FEATURE_COLUMNS)
        # Inverse-MAE blend sums to 1
        w = art["ensemble_weights"]
        assert pytest.approx(w["gbr"] + w["xgb"], abs=1e-6) == 1.0
        assert art["metrics"]["n_train"] + art["metrics"]["n_test"] == 80

    def test_train_rejects_missing_target(self):
        df = _training_set(n=20).drop(columns=[TARGET_COLUMN])
        with pytest.raises(ValueError, match="missing target column"):
            train_race_pace_model(df)

    def test_train_rejects_missing_feature_columns(self):
        df = _training_set(n=20).drop(columns=["tyre_age_laps"])
        with pytest.raises(ValueError, match="missing required columns"):
            train_race_pace_model(df)

    def test_train_rejects_undersized_input(self):
        df = _training_set(n=2)
        with pytest.raises(ValueError, match="at least 4 rows"):
            train_race_pace_model(df)

    def test_predict_outputs_one_value_per_row(self):
        df = _training_set(n=80)
        art = train_race_pace_model(df, test_size=0.25)
        # Use a clean inference frame derived from the same encoder space
        # (driver/team/circuit ids match because the training DF embeds them)
        preds = predict_lap_times(art, df.head(10))
        assert preds.shape == (10,)
        # All predictions should be physically plausible lap times (~75-90s)
        assert np.all(preds > 60.0)
        assert np.all(preds < 120.0)


class TestBuildTrainingDataset:
    def test_combines_multiple_sessions(self, monkeypatch: pytest.MonkeyPatch):
        # Two synthetic sessions; verify rows from both flow into the same DF.
        laps_a = _synthetic_laps_dataframe(n_drivers=2, n_laps=3)
        laps_b = _synthetic_laps_dataframe(n_drivers=2, n_laps=4)

        def fake_load(season: int, round_num: int):
            return SimpleNamespace(
                laps=laps_a if round_num == 1 else laps_b,
                weather_data=None,
                event={"Location": f"R{round_num}"},
            )

        monkeypatch.setattr(race_pace, "_load_race_session", fake_load)
        df, encoders = build_training_dataset([(2024, 1), (2024, 2)])
        # Round 1 = 2×3 = 6 rows; Round 2 = 2×4 = 8 rows → 14 total
        assert len(df) == 14
        # Both circuits should be in the encoder
        assert set(encoders["circuit"].keys()) == {"R1", "R2"}


class TestTrainRacePaceSkipGuard:
    """The trainer must no-op when a race-pace ensemble is already registered.

    Regression guard for the race-weekend cron death-spiral: re-fetching the
    full multi-season history on every poll exhausted the FastF1 rate limit and
    then crashed the live pipeline downstream.  When the sentinel binaries are
    present, ``main`` must return 0 WITHOUT ever calling ``build_training_dataset``
    (i.e. without touching FastF1); ``--force`` overrides.
    """

    def _seed_sentinel(self, root):
        import json
        from pathlib import Path

        d = Path(root) / "2025_round_99"
        d.mkdir(parents=True)
        (d / "metadata.json").write_text(json.dumps({"kind": "race-pace"}))
        (d / "race_pace_gbr.joblib").write_bytes(b"stub")

    def test_skips_when_already_registered(self, tmp_path, monkeypatch):
        import train_race_pace

        self._seed_sentinel(tmp_path)

        def _boom(*a, **k):  # must never be reached
            raise AssertionError("build_training_dataset called despite sentinel")

        monkeypatch.setattr(train_race_pace, "build_training_dataset", _boom)
        rc = train_race_pace.main(
            ["--seasons", "2018-2025", "--registry-root", str(tmp_path)]
        )
        assert rc == 0

    def test_force_bypasses_guard(self, tmp_path, monkeypatch):
        import train_race_pace

        self._seed_sentinel(tmp_path)
        called = {"n": 0}

        def _sentinel_call(pairs):
            called["n"] += 1
            # Return empty so main() exits early (rc=2) without training/saving.
            import pandas as pd

            return pd.DataFrame(), {}

        monkeypatch.setattr(train_race_pace, "build_training_dataset", _sentinel_call)
        rc = train_race_pace.main(
            ["--seasons", "2024", "--rounds", "1", "--registry-root", str(tmp_path), "--force"]
        )
        assert called["n"] == 1  # guard bypassed → dataset build attempted
        assert rc == 2  # empty df → documented "no lap data" exit

    def test_empty_registry_does_not_skip(self, tmp_path):
        import train_race_pace
        from models.registry import ModelRegistry

        assert train_race_pace._registered_race_pace(ModelRegistry(root=tmp_path)) is None

    def test_metadata_only_entry_is_not_treated_as_usable(self, tmp_path):
        # metadata.json without any binary must NOT count as registered.
        import json
        from pathlib import Path

        import train_race_pace
        from models.registry import ModelRegistry

        d = Path(tmp_path) / "2025_round_99"
        d.mkdir(parents=True)
        (d / "metadata.json").write_text(json.dumps({"kind": "race-pace"}))
        assert train_race_pace._registered_race_pace(ModelRegistry(root=tmp_path)) is None
