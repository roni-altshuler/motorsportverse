"""Le Mans predictor — implements the shared Predictor contract."""
from __future__ import annotations

from motorsport_core.interfaces import Predictor, RoundForecast

from .datasource import SportDataSource


class SportPredictor(Predictor):
    def fit(self, source: SportDataSource, season: int, upto_round: int) -> None:
        # TODO: train on rounds strictly < upto_round (leakage-safe).
        ...

    def predict(self, source: SportDataSource, season: int, round: int) -> RoundForecast:
        rnd = source.round(season, round)
        # TODO: produce a real ranked forecast.
        return RoundForecast(
            season=season, round=round, venue=__import__("motorsport_core.interfaces", fromlist=["Venue"]).Venue(key=rnd.venue.key, name=rnd.venue.name),
            predicted_order={},
        )
