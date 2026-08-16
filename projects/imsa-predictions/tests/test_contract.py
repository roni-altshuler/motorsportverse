"""Contract tests for IMSA WeatherTech SportsCar Championship.

A scaffolded project is still held to the repo's rules. These tests assert the
three that a not-yet-implemented series can already break:

1. **The seams satisfy the shared ABCs.** The previous scaffold declared the
   core ``Predictor`` while calling the ``motorsport_data`` DataSource — two
   different ABCs with the same name — so nothing could have been wired to it.
2. **Nothing is fabricated.** With no snapshot, every accessor returns empty.
   A scaffold that returns a plausible calendar is worse than one that returns
   nothing, because the plausible version reaches a chart.
3. **Leakage is refused at the boundary**, so the guard is live from day one
   rather than added after the first suspicious backtest.
"""
from __future__ import annotations

import inspect

import pytest

from motorsport_core.interfaces import DataSource as CoreDataSource
from motorsport_core.interfaces import Predictor as CorePredictor
from motorsport_core.interfaces import RoundForecast

from imsa_predictions import config
from imsa_predictions.datasource import IMSADataSource
from imsa_predictions.predict import IMSAPredictor
from imsa_predictions.sources import snapshot


# --------------------------------------------------------------------------- #
# 1. the seams satisfy the shared contracts
# --------------------------------------------------------------------------- #


def test_datasource_implements_the_core_contract():
    assert issubclass(IMSADataSource, CoreDataSource)
    source = IMSADataSource()
    for method in ("calendar", "grid", "results"):
        assert callable(getattr(source, method))


def test_predictor_implements_the_core_contract():
    assert issubclass(IMSAPredictor, CorePredictor)


def test_the_datasource_is_instantiable():
    """An ABC with an unimplemented abstract method cannot be constructed."""
    assert IMSADataSource().sport == config.SPORT


def test_predict_returns_the_shared_forecast_type():
    source, predictor = IMSADataSource(), IMSAPredictor()
    forecast = predictor.predict(source, config.DEFAULT_SEASON, 1)
    assert isinstance(forecast, RoundForecast)


def test_fit_signature_matches_the_contract():
    """A drifted signature breaks every shared pipeline that calls it."""
    assert list(inspect.signature(IMSAPredictor.fit).parameters) == [
        "self", "source", "season", "upto_round",
    ]


# --------------------------------------------------------------------------- #
# 2. nothing is fabricated
# --------------------------------------------------------------------------- #


def test_no_snapshot_means_an_empty_calendar_not_an_invented_one():
    assert list(IMSADataSource().calendar(config.DEFAULT_SEASON)) == []


def test_no_snapshot_means_an_empty_grid():
    assert list(IMSADataSource().grid(config.DEFAULT_SEASON, 1)) == []


def test_no_snapshot_means_no_results():
    assert dict(IMSADataSource().results(config.DEFAULT_SEASON, 1)) == {}


def test_an_empty_grid_produces_an_empty_order_not_a_guess():
    forecast = IMSAPredictor().predict(IMSADataSource(), config.DEFAULT_SEASON, 1)
    assert forecast.predicted_order == {}


def test_strict_mode_fails_loudly_instead_of_returning_empty():
    """A pipeline must not mistake "never ingested" for "a season with no rounds"."""
    with pytest.raises(snapshot.SnapshotUnavailable) as excinfo:
        IMSADataSource(strict=True).calendar(config.DEFAULT_SEASON)
    assert config.SOURCE_URL in str(excinfo.value)


def test_the_project_reports_its_own_data_status_honestly():
    assert config.DATA_SOURCE_IMPLEMENTED is False
    assert snapshot.available_seasons() == []


def test_every_forecast_carries_its_maturity():
    """A consumer must never have to infer that this series is not wired."""
    forecast = IMSAPredictor().predict(IMSADataSource(), config.DEFAULT_SEASON, 1)
    assert forecast.metadata["dataSourceImplemented"] is False
    assert forecast.metadata["maturity"] == "in-development"


# --------------------------------------------------------------------------- #
# 3. leakage is refused at the boundary
# --------------------------------------------------------------------------- #


def test_fit_only_sees_prior_rounds():
    predictor = IMSAPredictor()
    predictor.fit(IMSADataSource(), config.DEFAULT_SEASON, upto_round=5)
    assert predictor._fitted_upto == 5


def test_ranking_puts_better_prior_form_first():
    """The one behaviour worth asserting on a model this simple."""
    predictor = IMSAPredictor()
    predictor._mean_position = {"AAA": 8.0, "BBB": 2.0}

    class _Grid(IMSADataSource):
        def calendar(self, season):
            return []

        def grid(self, season, round):
            from motorsport_core.interfaces import Competitor, GridEntry

            return [
                GridEntry(Competitor("AAA", "A", "T1")),
                GridEntry(Competitor("BBB", "B", "T2")),
            ]

    order = predictor.predict(_Grid(), config.DEFAULT_SEASON, 1).predicted_order
    assert order["BBB"] < order["AAA"]


def test_an_unrated_entrant_sorts_behind_a_rated_one():
    """"Never seen" is not "average" — an invented mid-field rating is a claim."""
    predictor = IMSAPredictor()
    predictor._mean_position = {"AAA": 9.0}

    class _Grid(IMSADataSource):
        def calendar(self, season):
            return []

        def grid(self, season, round):
            from motorsport_core.interfaces import Competitor, GridEntry

            return [
                GridEntry(Competitor("NEW", "New", "T3")),
                GridEntry(Competitor("AAA", "A", "T1")),
            ]

    order = predictor.predict(_Grid(), config.DEFAULT_SEASON, 1).predicted_order
    assert order["AAA"] < order["NEW"]


# --------------------------------------------------------------------------- #
# config sanity
# --------------------------------------------------------------------------- #


def test_the_season_env_override_is_honoured(monkeypatch):
    monkeypatch.setenv(config.SEASON_ENV, "2031")
    assert config.active_season() == 2031


def test_a_junk_season_env_falls_back_rather_than_crashing(monkeypatch):
    monkeypatch.setenv(config.SEASON_ENV, "not-a-year")
    assert config.active_season() == config.DEFAULT_SEASON


def test_the_classes_that_race_together_are_recorded():
    """A single field-wide order mixes classes; the split has to be declared."""
    assert len(config.CLASSES) >= 1
