"""FE predictor — implements the shared ``motorsport_core.interfaces.Predictor``.

Thin adapter: it conforms FE to the ecosystem contract and delegates the actual
work to :mod:`formula_e_predictions.pipeline` (which is itself mostly calls
into motorsport-core). This is what lets the FE project drop into any
core-driven harness that expects a ``Predictor``.
"""
from __future__ import annotations

from motorsport_core.interfaces import Predictor, RoundForecast, Venue

from . import config, pipeline
from .datasource import FEDataSource


class FEPredictor(Predictor):
    def __init__(self) -> None:
        self._fitted_upto: int | None = None

    def fit(self, source: FEDataSource, season: int, upto_round: int) -> None:
        # Skill is estimated lazily per-round from prior results (leakage-safe
        # in model.estimate_skill), so "fitting" just records the boundary.
        self._fitted_upto = upto_round

    def predict(self, source: FEDataSource, season: int, round: int) -> RoundForecast:
        fc = pipeline.forecast_round(source, season, round)
        order = {code: pos for pos, code in enumerate(fc.race.order, start=1)}
        return RoundForecast(
            season=season,
            round=round,
            venue=Venue(key=fc.venue_key, name=fc.venue_name),
            predicted_order=order,
            probabilities=fc.race.markets,
            metadata={
                "sport": config.SPORT,
                "qualifying_order": fc.race.grid,
                "venue_kind": fc.venue_kind,
            },
        )


# Back-compat alias for the scaffolded template name.
SportPredictor = FEPredictor
