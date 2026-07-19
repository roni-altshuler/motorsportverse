"""Offline lap-cache behaviour for the historical driver-pace features.

Regression guard for the race-weekend cron crash: the FastF1 live-timing API is
unreachable from CI runners, so ``load_race_session`` must serve immutable past
seasons from the committed snapshot under ``features/data/lap_cache/`` WITHOUT
touching the network, and persist a snapshot when it does fetch live.
"""
from __future__ import annotations

import pandas as pd

import f1_prediction_utils as fpu


def _fake_snapshot(year: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Driver": ["VER", "HAM"],
            "LapTime": pd.to_timedelta(["0:01:45", "0:01:46"]),
            "Sector1Time": pd.to_timedelta(["0:00:30", "0:00:31"]),
            "Sector2Time": pd.to_timedelta(["0:00:35", "0:00:35"]),
            "Sector3Time": pd.to_timedelta(["0:00:40", "0:00:40"]),
            "LapTime (s)": [105.0, 106.0],
            "Sector1Time (s)": [30.0, 31.0],
            "Sector2Time (s)": [35.0, 35.0],
            "Sector3Time (s)": [40.0, 40.0],
            "Year": [year, year],
        }
    )


class TestLapCacheOffline:
    def test_reads_snapshot_without_touching_fastf1(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fpu, "LAP_CACHE_DIR", tmp_path)
        path = fpu._lap_cache_path(2024, "Belgium", "R")
        _fake_snapshot(2024).to_parquet(path, index=False)

        def _boom(*a, **k):  # must never be reached
            raise AssertionError("fastf1.get_session called despite snapshot")

        monkeypatch.setattr(fpu.fastf1, "get_session", _boom)

        laps = fpu.load_race_session(2024, "Belgium", "R")
        assert len(laps) == 2
        assert set(laps["Driver"]) == {"VER", "HAM"}

    def test_aliased_circuit_shares_one_snapshot(self, tmp_path, monkeypatch):
        # Madrid resolves to Spain (HISTORICAL_GP_ALIASES) → same snapshot file.
        monkeypatch.setattr(fpu, "LAP_CACHE_DIR", tmp_path)
        assert fpu._lap_cache_path(2024, "Madrid", "R") == fpu._lap_cache_path(
            2024, "Spain", "R"
        )

    def test_live_fetch_persists_snapshot(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fpu, "LAP_CACHE_DIR", tmp_path)
        raw = pd.DataFrame(
            {
                "Driver": ["VER"],
                "LapTime": pd.to_timedelta(["0:01:45"]),
                "Sector1Time": pd.to_timedelta(["0:00:30"]),
                "Sector2Time": pd.to_timedelta(["0:00:35"]),
                "Sector3Time": pd.to_timedelta(["0:00:40"]),
            }
        )

        class _FakeSession:
            laps = raw

            def load(self, **kwargs):
                return None

        monkeypatch.setattr(fpu.fastf1, "get_session", lambda *a, **k: _FakeSession())

        laps = fpu.load_race_session(2099, "Belgium", "R")
        assert "LapTime (s)" in laps.columns
        # Snapshot written so future (offline) runs read it back.
        assert fpu._lap_cache_path(2099, "Belgium", "R").exists()
        reread = pd.read_parquet(fpu._lap_cache_path(2099, "Belgium", "R"))
        assert reread["LapTime (s)"].iloc[0] == 105.0
