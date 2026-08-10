"""WRC predictor — the shared ``Predictor`` contract over the real model.

A thin adapter that delegates to :func:`wrc_predictions.model.forecast_round` (the
surface-aware skill model ensembled with championship form) and packs the rally
classification forecast into the core :class:`RoundForecast`. Rally has no
qualifying grid, so there is no post-quali surface — the forecast is driven by
cross-season form, the car, and same-surface history.
"""
from __future__ import annotations

from motorsport_core.interfaces import Predictor, RoundForecast, Venue

from . import config, model
from .datasource import WrcDataSource


class WrcPredictor(Predictor):
    def __init__(self) -> None:
        self._upto: int | None = None

    def fit(self, source: WrcDataSource, season: int, upto_round: int) -> None:
        self._upto = upto_round  # non-parametric; Elo replay happens at predict time

    def predict(self, source: WrcDataSource, season: int, round: int) -> RoundForecast:
        fc = model.forecast_round(source, season, round)
        predicted_order = {code: i + 1 for i, code in enumerate(fc.rally.order)}
        venue = source._venue(round)
        return RoundForecast(
            season=season,
            round=round,
            venue=Venue(key=venue.key, name=venue.name, country=venue.country, kind="stage"),
            predicted_order=predicted_order,
            probabilities=fc.rally.markets,
            metadata={"sport": config.SPORT, "surface": fc.surface},
        )


# Backwards-compatible alias (the stub exported ``SportPredictor``).
SportPredictor = WrcPredictor
