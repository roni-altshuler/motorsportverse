"""Tests for the Open-Meteo weather integration.

We never hit the network: ``urllib.request.urlopen`` is mocked end-to-end.
A-P1.4 is mostly an existing module (weather_api.py); these tests close
the test-coverage gap and lock the public contract so the race simulator
(Step 3 integration) can consume forecasts confidently.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from weather_api import (
    CIRCUIT_COORDINATES,
    STATIC_WEATHER,
    WeatherService,
    _wmo_description,
)


# --------------------------------------------------------------------------- #
# Synthetic Open-Meteo response fixture
# --------------------------------------------------------------------------- #


def _open_meteo_payload(
    *,
    hours: list[int] | None = None,
    temps: list[float] | None = None,
    rain_probs: list[float] | None = None,
    precip: list[float] | None = None,
    weather_codes: list[int] | None = None,
) -> dict:
    """Build a minimal-but-realistic Open-Meteo hourly response.

    Only the fields ``_fetch_from_api`` reads are populated.  Anything
    missing falls back to safe defaults in the parser, which is part of
    what we test.
    """
    hours = hours or list(range(0, 24))
    n = len(hours)
    temps = temps or [22.0 + i * 0.3 for i in range(n)]
    rain_probs = rain_probs or [10.0 if 14 <= h <= 17 else 5.0 for h in hours]
    precip = precip or [0.0] * n
    weather_codes = weather_codes or [0] * n
    return {
        "hourly": {
            "time": [f"2026-05-25T{h:02d}:00" for h in hours],
            "temperature_2m": temps,
            "relative_humidity_2m": [60.0] * n,
            "precipitation_probability": rain_probs,
            "precipitation": precip,
            "wind_speed_10m": [12.0] * n,
            "wind_direction_10m": [180] * n,
            "cloud_cover": [40] * n,
            "weather_code": weather_codes,
        },
        "daily": {
            "precipitation_probability_max": [max(rain_probs)],
            "temperature_2m_max": [max(temps)],
            "temperature_2m_min": [min(temps)],
        },
    }


def _mock_urlopen_with(payload: dict):
    """Return a context manager that mocks urlopen → payload."""

    class _FakeResponse:
        def __init__(self, data: bytes) -> None:
            self._buf = BytesIO(data)

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *_: Any) -> None:
            pass

    body = json.dumps(payload).encode("utf-8")
    return patch(
        "weather_api.urllib.request.urlopen",
        return_value=_FakeResponse(body),
    )


# --------------------------------------------------------------------------- #
# CIRCUIT_COORDINATES integrity
# --------------------------------------------------------------------------- #


class TestCircuitCoordinates:
    def test_every_circuit_has_lat_lon_timezone(self):
        for gp_key, coords in CIRCUIT_COORDINATES.items():
            assert "lat" in coords, f"{gp_key}: missing lat"
            assert "lon" in coords, f"{gp_key}: missing lon"
            assert "timezone" in coords, f"{gp_key}: missing timezone"
            assert -90 <= coords["lat"] <= 90
            assert -180 <= coords["lon"] <= 180

    def test_static_weather_keys_align_with_coordinates(self):
        # Drop "Madrid" / any future-circuit additions — STATIC_WEATHER must
        # at least cover the same locations as CIRCUIT_COORDINATES.
        missing = set(CIRCUIT_COORDINATES) - set(STATIC_WEATHER)
        # Not strict equality — the project ships unequal sets when new
        # circuits land; we only require static fallbacks for circuits we
        # know GPS for.
        assert missing == set() or missing.issubset({"Madrid"}), (
            f"missing static fallbacks for {missing}"
        )


# --------------------------------------------------------------------------- #
# Race-window aggregation
# --------------------------------------------------------------------------- #


class TestRaceForecastFetch:
    def test_returns_race_window_aggregate(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        # Race window (14:00-17:00) gets temps 28, 29, 30, 31 — average should be 29.5
        payload = _open_meteo_payload(
            hours=list(range(0, 24)),
            temps=[
                15.0 if h < 14 else 28.0 + (h - 14) for h in range(24)
            ],
        )
        with _mock_urlopen_with(payload):
            result = ws.get_race_forecast("Monaco", "2026-05-25")
        assert result["source"] == "api"
        assert result["gp_key"] == "Monaco"
        # Temperature averaged over 14:00-17:00 → (28+29+30+31)/4 = 29.5
        assert result["temperature_c"] == pytest.approx(29.5, abs=0.1)

    def test_rain_probability_is_normalised_to_unit_interval(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        payload = _open_meteo_payload(
            rain_probs=[80.0 if 14 <= h <= 17 else 20.0 for h in range(24)],
        )
        with _mock_urlopen_with(payload):
            result = ws.get_race_forecast("Belgium", "2026-05-25")
        assert 0.0 <= result["rain_probability"] <= 1.0
        assert result["rain_probability"] == pytest.approx(0.80, abs=0.01)

    def test_forecast_detail_only_covers_race_window(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        with _mock_urlopen_with(_open_meteo_payload()):
            result = ws.get_race_forecast("Spain", "2026-05-25")
        # Race window is 14:00-17:00 inclusive → 4 hourly entries
        assert len(result["forecast_detail"]) == 4
        for entry in result["forecast_detail"]:
            hour = int(entry["time"].split("T")[1].split(":")[0])
            assert 14 <= hour <= 17


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #


class TestForecastCache:
    def test_second_call_within_ttl_reads_from_cache(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        with _mock_urlopen_with(_open_meteo_payload()):
            first = ws.get_race_forecast("Monaco", "2026-05-25")
            # Second call must NOT hit the network — patch is gone the moment
            # we exit the with-block.  If the cache works, this won't 500.
        second = ws.get_race_forecast("Monaco", "2026-05-25")
        assert first["temperature_c"] == second["temperature_c"]
        assert second["source"] == "cache"

    def test_stale_cache_falls_back_to_static(self, tmp_path: Path):
        """6-hour TTL: if a cached record is older than that the service
        re-fetches; with the mock gone it should fall back to static."""
        ws = WeatherService(cache_dir=str(tmp_path))
        cache_file = tmp_path / "Monaco_2026-05-25.json"
        # Forge a stale cache record
        stale_ts = (datetime.now() - timedelta(hours=12)).isoformat()
        cache_file.write_text(
            json.dumps({"temperature_c": 99.0, "cached_at": stale_ts, "source": "api"})
        )
        # No mock — urlopen will fail.  Service should fall back to static.
        with patch(
            "weather_api.urllib.request.urlopen",
            side_effect=RuntimeError("network down"),
        ):
            result = ws.get_race_forecast("Monaco", "2026-05-25")
        assert result["source"] == "static"


# --------------------------------------------------------------------------- #
# Fallbacks
# --------------------------------------------------------------------------- #


class TestFallbacks:
    def test_unknown_circuit_falls_back_to_static(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        result = ws.get_race_forecast("UnknownGP", "2026-05-25")
        assert result["source"] == "static"
        # Generic static defaults — the service must always return something
        # the consumer can use.
        assert "rain_probability" in result
        assert "temperature_c" in result

    def test_api_error_falls_back_to_static(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        with patch(
            "weather_api.urllib.request.urlopen",
            side_effect=RuntimeError("simulated timeout"),
        ):
            result = ws.get_race_forecast("Monaco", "2026-05-25")
        assert result["source"] == "static"


# --------------------------------------------------------------------------- #
# WMO description
# --------------------------------------------------------------------------- #


class TestWMODescription:
    @pytest.mark.parametrize(
        ("code", "expected_substring"),
        [
            (0, "Clear sky"),
            (3, "Overcast"),
            (61, "rain"),
            (95, "Thunderstorm"),
            (999, "Unknown"),
        ],
    )
    def test_returns_description_or_unknown(self, code: int, expected_substring: str):
        assert expected_substring in _wmo_description(code)


# --------------------------------------------------------------------------- #
# get_all_race_forecasts
# --------------------------------------------------------------------------- #


class TestBulkForecasts:
    def test_returns_one_entry_per_round(self, tmp_path: Path):
        ws = WeatherService(cache_dir=str(tmp_path))
        calendar = {
            1: {"gp_key": "Monaco", "date": "2026-05-25"},
            2: {"gp_key": "Spain", "date": "2026-06-01"},
        }
        with _mock_urlopen_with(_open_meteo_payload()):
            forecasts = ws.get_all_race_forecasts(calendar)
        assert set(forecasts.keys()) == {"Monaco", "Spain"}
        for gp_key, fc in forecasts.items():
            assert "rain_probability" in fc
            assert "temperature_c" in fc
