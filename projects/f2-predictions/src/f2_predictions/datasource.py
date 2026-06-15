"""F2 data source.

Implements the shared ``motorsport_data.sources.base.DataSource`` contract.

F2 has no open Ergast/Jolpica feed, so results come from a **reproducible
latent-pace model** (see ``config._TRUTH_PACE``): each scored race is a
Plackett-Luce-style draw from latent pace plus seeded per-race noise. The draw
is deterministic in ``(season, round, race_index)`` so the "season so far" is
stable across runs and tests. Replace :meth:`results` with a live feed (FastF1
F2 / official timing) to make this a live product — nothing else changes.
"""
from __future__ import annotations

import numpy as np

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config


class F2DataSource(DataSource):
    sport = config.SPORT

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
        """Classified order for a scored race.

        ``race_index`` 0 = sprint, 1 = feature. Returns [] for rounds not yet run.
        """
        if round > config.COMPLETED_ROUNDS or round < 1:
            return []
        order = self._sample_order(year, round, race_index)
        return [
            Result(competitor=code, position=pos, grid=pos, status="Finished", points=None)
            for pos, code in enumerate(order, start=1)
        ]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _venue(self, round: int) -> Venue:
        idx = round - 1
        return config.CALENDAR[idx] if 0 <= idx < len(config.CALENDAR) else config.CALENDAR[0]

    def _sample_order(self, year: int, round: int, race_index: int) -> list[str]:
        """Deterministic finishing order from latent pace + seeded noise."""
        codes = list(config._TRUTH_PACE.keys())
        pace = np.array([config._TRUTH_PACE[c] for c in codes], dtype=float)
        # Seed is a stable function of (year, round, race_index).
        seed = (year * 1000 + round * 10 + race_index) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        # Per-race noise (qualifying variance + race incidents).
        noise = rng.normal(0.0, 0.45, size=pace.shape)
        effective = pace + noise
        ranked_idx = np.argsort(effective)
        return [codes[i] for i in ranked_idx]

    def race_results_for_round(self, year: int, round: int) -> dict[str, list[Result]]:
        """Both scored races for a completed round: {'sprint': [...], 'feature': [...]}."""
        return {
            "sprint": self.results(year, round, race_index=0),
            "feature": self.results(year, round, race_index=1),
        }
