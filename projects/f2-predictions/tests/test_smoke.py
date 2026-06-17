"""Smoke tests: F2 imports, wires to the shared core, registry entry valid."""

import json
from pathlib import Path


def test_imports_and_predict_wires_core():
    from f2_predictions.datasource import F2DataSource
    from f2_predictions.predict import F2Predictor

    src = F2DataSource()
    pred = F2Predictor()
    pred.fit(src, 2026, upto_round=8)
    forecast = pred.predict(src, 2026, round=8)

    assert forecast.season == 2026
    assert forecast.predicted_order
    assert forecast.probabilities is not None
    assert abs(sum(forecast.probabilities.p_win.values()) - 1.0) < 1e-6


def test_datasource_calendar_uses_shared_schema():
    from motorsport_data.schema import Season

    from f2_predictions.datasource import F2DataSource

    season = F2DataSource().season(2026)
    assert isinstance(season, Season)
    assert season.sport == "Formula 2"
    assert len(season.calendar) >= 10
    assert len(season.competitors) == 22


def test_registry_entry_valid():
    root = Path(__file__).resolve().parents[3]
    entry = json.loads((root / "registry" / "projects" / "f2-predictions.json").read_text())
    assert entry["slug"] == "f2-predictions"
    assert entry["maturity"] in {"in-development", "experimental", "production"}
    assert entry["sport"] == "Formula 2"
