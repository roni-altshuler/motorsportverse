"""FIA World Endurance Championship predictor — the shared ``Predictor`` contract.

A thin project on a proven core: this supplies only a fit procedure and a
ranking, and everything numerically heavy (calibration, championship Monte
Carlo, evaluation, drift, promotion) comes from ``motorsport-core`` unchanged.

The model here is deliberately the SIMPLEST honest one — a prior-form ranking
over completed rounds. It is not a placeholder that returns nothing: it works
the moment a snapshot exists, and it is exactly the "can the shared core beat a
trivial baseline for this sport" experiment that has to run before anything
more elaborate is justified. See the README for the format-specific problems
this model does **not** solve.

**Leakage is enforced at the boundary**, not trusted to a filter written at the
call site: :func:`fit` asserts through ``motorsport_core.leakage.assert_prior_only``.
"""
from __future__ import annotations

from typing import Mapping

from motorsport_core.interfaces import Predictor, RoundForecast, Venue
from motorsport_core.leakage import assert_prior_only

from . import config
from .datasource import WECDataSource


class WECPredictor(Predictor):
    """Ranks by mean prior finishing position. The baseline to beat, not the goal."""

    def __init__(self) -> None:
        self._mean_position: dict[str, float] = {}
        self._fitted_upto: int | None = None

    def fit(self, source: WECDataSource, season: int, upto_round: int) -> None:
        """Train on rounds strictly BEFORE ``upto_round``.

        The prior-only assertion runs on the collected map rather than being
        assumed from the loop bound: a rolling feature computed over a window
        that includes the round being predicted produces output that looks
        entirely normal, which is why every project in this repo asserts at the
        boundary instead of trusting its own range.
        """
        history: dict[int, Mapping[str, int]] = {}
        for rnd in range(1, upto_round):
            results = source.results(season, rnd)
            if results:
                history[rnd] = results
        assert_prior_only(history, upto_round, label=f"{config.SHORT_NAME} fit")

        totals: dict[str, list[int]] = {}
        for results in history.values():
            for code, position in results.items():
                totals.setdefault(code, []).append(position)
        self._mean_position = {
            code: sum(positions) / len(positions) for code, positions in totals.items()
        }
        self._fitted_upto = upto_round

    def predict(self, source: WECDataSource, season: int, round: int) -> RoundForecast:
        """Forecast one round. An empty grid yields an EMPTY order, not a guess."""
        calendar = source.calendar(season)
        venue = (
            calendar[round - 1]
            if 1 <= round <= len(calendar)
            else Venue(key=f"round-{round}", name=f"Round {round}")
        )
        grid = source.grid(season, round)

        # Unrated entrants sort behind rated ones rather than being assigned an
        # invented mid-field rating: "we have never seen this car" and "this car
        # is average" are different claims.
        rated = [e for e in grid if e.competitor.code in self._mean_position]
        unrated = [e for e in grid if e.competitor.code not in self._mean_position]
        rated.sort(key=lambda e: self._mean_position[e.competitor.code])
        unrated.sort(key=lambda e: (e.grid_position is None, e.grid_position or 0))

        order = {
            entry.competitor.code: position
            for position, entry in enumerate([*rated, *unrated], start=1)
        }
        return RoundForecast(
            season=season,
            round=round,
            venue=venue,
            predicted_order=order,
            metadata={
                "model": "prior-form-mean",
                "sport": config.SPORT,
                "fittedUptoRound": self._fitted_upto,
                "ratedCompetitors": len(rated),
                "unratedCompetitors": len(unrated),
                # Stated on every forecast so no consumer has to infer it.
                "dataSourceImplemented": config.DATA_SOURCE_IMPLEMENTED,
                "maturity": "in-development",
            },
        )


__all__ = ["WECPredictor"]
