"""F2 data source — calendar/roster from config, results from a selectable feed.

Implements the shared ``motorsport_data.sources.base.DataSource`` contract. The
calendar and roster always come from :mod:`config`; the *results* come from a
source selected at construction:

- default (``F2_USE_LIVE_RESULTS`` unset/``"0"``): the deterministic synthetic
  source — identical behaviour to Phase 1, so CI and tests stay reproducible;
- live (``F2_USE_LIVE_RESULTS="1"``): a :class:`CompositeF2Source` that tries the
  real feeds (FastF1 → official) and falls back to synthetic, recording per-race
  provenance.

The public surface (``season`` / ``round`` / ``results`` / ``race_results_for_round``)
is unchanged, so the pipeline, model, and export are agnostic to where results
come from — the whole point of the source seam.
"""
from __future__ import annotations

import os

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config
from .sources import CompositeF2Source, SyntheticF2Source


def _live_enabled() -> bool:
    return os.getenv("F2_USE_LIVE_RESULTS", "0") == "1"


class F2DataSource(DataSource):
    sport = config.SPORT

    def __init__(self, *, live: bool | None = None):
        use_live = _live_enabled() if live is None else live
        self._source = CompositeF2Source.default() if use_live else SyntheticF2Source()

    # ------------------------------------------------------------------ #
    def season(self, year: int = config.SEASON) -> Season:
        return Season(
            sport=config.SPORT,
            year=year,
            competitors=[
                Competitor(code=d["code"], name=d["name"], team=d["team"])
                for d in config.DRIVERS
            ],
            teams=config.TEAMS,
            calendar=config.CALENDAR,
            completed_rounds=list(range(1, config.COMPLETED_ROUNDS + 1)),
        )

    def round(self, year: int, round: int) -> Round:
        venue = self._venue(round)
        completed = round <= config.COMPLETED_ROUNDS
        results = self.results(year, round) if completed else []
        return Round(season=year, round=round, venue=venue, completed=completed, results=results)

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result]:
        """Classified order for a scored race. ``race_index`` 0 = sprint, 1 = feature.
        Returns ``[]`` for rounds not yet run (leakage-safe)."""
        if round > config.COMPLETED_ROUNDS or round < 1:
            return []
        res = self._source.results(year, round, race_index)
        return res if res is not None else []

    def race_results_for_round(self, year: int, round: int) -> dict[str, list[Result]]:
        """Both scored races for a completed round: {'sprint': [...], 'feature': [...]}."""
        return {
            "sprint": self.results(year, round, race_index=0),
            "feature": self.results(year, round, race_index=1),
        }

    def provenance(self, year: int, round: int, race_index: int = 1) -> str:
        """Which source served this race's results — 'synthetic' | 'fastf1' | 'official'.

        Used by the honest calibration gate to count only *real* rounds.
        """
        src = self._source
        if hasattr(src, "provenance"):
            return src.provenance(year, round, race_index)
        return getattr(src, "name", "synthetic")

    # ------------------------------------------------------------------ #
    def _venue(self, round: int) -> Venue:
        idx = round - 1
        return config.CALENDAR[idx] if 0 <= idx < len(config.CALENDAR) else config.CALENDAR[0]
