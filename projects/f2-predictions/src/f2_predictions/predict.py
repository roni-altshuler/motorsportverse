"""F2 predictor — implements the shared ``motorsport_core.interfaces.Predictor``.

Thin adapter: it conforms F2 to the ecosystem contract and delegates the actual
work to :mod:`f2_predictions.pipeline` (which is itself mostly calls into
motorsport-core). This is what lets the F2 project drop into any core-driven
harness that expects a ``Predictor``.
"""
from __future__ import annotations

from motorsport_core.interfaces import Predictor, RoundForecast, Venue

from . import config, pipeline
from .datasource import F2DataSource


class F2Predictor(Predictor):
    def __init__(self) -> None:
        self._fitted_upto: int | None = None

    def fit(self, source: F2DataSource, season: int, upto_round: int) -> None:
        # Skill is estimated lazily per-round from prior results (leakage-safe in
        # model.estimate_skill), so "fitting" just records the boundary.
        self._fitted_upto = upto_round

    def predict(self, source: F2DataSource, season: int, round: int) -> RoundForecast:
        fc = pipeline.forecast_round(source, season, round)
        order = {code: pos for pos, code in enumerate(fc.feature.order, start=1)}
        return RoundForecast(
            season=season,
            round=round,
            venue=Venue(key=fc.venue_key, name=fc.venue_name),
            predicted_order=order,
            probabilities=fc.feature.markets,
            metadata={
                "sport": config.SPORT,
                "qualifying_order": fc.feature.grid,
                "sprint_order": fc.sprint.order,
            },
        )
