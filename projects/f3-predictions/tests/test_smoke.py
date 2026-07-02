"""Smoke tests: F3 imports, wires to the shared core, registry entry valid."""

import json
from pathlib import Path


def test_imports_and_predict_wires_core():
    from f3_predictions.datasource import F3DataSource
    from f3_predictions.predict import F3Predictor

    src = F3DataSource()
    pred = F3Predictor()
    pred.fit(src, 2026, upto_round=8)
    forecast = pred.predict(src, 2026, round=8)

    assert forecast.season == 2026
    assert forecast.predicted_order
    assert forecast.probabilities is not None
    assert abs(sum(forecast.probabilities.p_win.values()) - 1.0) < 1e-6


def test_datasource_calendar_uses_shared_schema():
    from motorsport_data.schema import Season

    from f3_predictions.datasource import F3DataSource

    season = F3DataSource().season(2026)
    assert isinstance(season, Season)
    assert season.sport == "Formula 3"
    from f3_predictions import config

    assert len(season.calendar) == len(config.CALENDAR)
    assert len(season.competitors) == len(config.DRIVERS)


def test_registry_entry_valid():
    root = Path(__file__).resolve().parents[3]
    entry = json.loads((root / "registry" / "projects" / "f3-predictions.json").read_text())
    assert entry["slug"] == "f3-predictions"
    assert entry["maturity"] in {"in-development", "experimental", "production"}
    assert entry["sport"] == "Formula 3"
