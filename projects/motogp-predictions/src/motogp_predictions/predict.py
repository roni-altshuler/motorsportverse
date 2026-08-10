"""MotoGP predictor — the shared ``Predictor`` contract over the real model.

A thin adapter: it delegates to :func:`motogp_predictions.model.forecast_round`
(cross-season Elo + manufacturer-weighted pace → Plackett-Luce markets) and packs
the Grand Prix (feature) forecast into the core :class:`RoundForecast`. The
forecast conditions on the real qualifying grid whenever it is published — the
post-quali surface validated to beat the raw-grid baseline (see
``config.GRID_WEIGHT``).
"""
from __future__ import annotations

from motorsport_core.interfaces import Predictor, RoundForecast, Venue

from . import config, model
from .datasource import MotoGPDataSource


class MotoGPPredictor(Predictor):
    def __init__(self) -> None:
        self._upto: int | None = None

    def fit(self, source: MotoGPDataSource, season: int, upto_round: int) -> None:
        # The model is non-parametric over prior results (Elo replay happens at
        # predict time, leakage-guarded), so "fit" just records the cutoff.
        self._upto = upto_round

    def predict(self, source: MotoGPDataSource, season: int, round: int) -> RoundForecast:
        known_grid = source.qualifying(season, round)
        fc = model.forecast_round(source, season, round, known_grid=known_grid)
        predicted_order = {code: i + 1 for i, code in enumerate(fc.feature.order)}
        venue = source._venue(round)
        return RoundForecast(
            season=season,
            round=round,
            venue=Venue(key=venue.key, name=venue.name, country=venue.country),
            predicted_order=predicted_order,
            probabilities=fc.feature.markets,
            metadata={
                "grid_provenance": "real-quali" if known_grid else "estimated",
                "sport": config.SPORT,
            },
        )


# Backwards-compatible alias (the stub exported ``SportPredictor``).
SportPredictor = MotoGPPredictor
