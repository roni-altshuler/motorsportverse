"""F2 data source — calendar/roster from config, results from a selectable feed.

Implements the shared ``motorsport_data.sources.base.DataSource`` contract. The
calendar and roster always come from :mod:`config`; the *results* come from a
source selected at construction:

- default (``F2_USE_LIVE_RESULTS`` unset/``"0"``): the **real** committed
  snapshot (``data/official_2026.json``, scraped from fiaformula2.com by
  :mod:`refresh`) for completed rounds, with the deterministic synthetic
  generator behind it for any round the snapshot is missing — offline and
  reproducible, so CI/tests stay deterministic while shipping real data;
- live (``F2_USE_LIVE_RESULTS="1"``): a :class:`CompositeF2Source` that scrapes
  the live FIA site first, then the snapshot, then synthetic.

The set of *completed* rounds is **derived from the feed** (the leading run of
rounds that actually return results), not a hardcoded constant. Tests can inject
a source directly via ``F2DataSource(source=...)``.
"""
from __future__ import annotations

import os

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config
from .sources import CompositeF2Source


def _live_enabled() -> bool:
    return os.getenv("F2_USE_LIVE_RESULTS", "0") == "1"


class F2DataSource(DataSource):
    sport = config.SPORT

    def __init__(self, *, live: bool | None = None, source=None):
        if source is not None:
            self._source = source
        elif _live_enabled() if live is None else live:
            self._source = CompositeF2Source.live()
        else:
            self._source = CompositeF2Source.default()
        self._completed_cache: dict[int, list[int]] = {}

    # ------------------------------------------------------------------ #
    def completed_rounds(self, year: int = config.SEASON) -> list[int]:
        """Rounds with published results — the leading run of scored rounds.

        Derived from the feed: a round counts as completed once its feature race
        returns a non-empty classification. F2 rounds complete in order, so we
        stop at the first round with no results.
        """
        if year not in self._completed_cache:
            done: list[int] = []
            for rnd in range(1, len(config.CALENDAR) + 1):
                res = self._source.results(year, rnd, race_index=1)
                if res:
                    done.append(rnd)
                else:
                    break
            self._completed_cache[year] = done
        return self._completed_cache[year]

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
            completed_rounds=self.completed_rounds(year),
        )

    def round(self, year: int, round: int) -> Round:
        venue = self._venue(round)
        completed = round in self.completed_rounds(year)
        results = self.results(year, round) if completed else []
        return Round(season=year, round=round, venue=venue, completed=completed, results=results)

    def results(self, year: int, round: int, race_index: int = 1) -> list[Result]:
        """Classified order for a scored race. ``race_index`` 0 = sprint, 1 = feature.
        Returns ``[]`` for rounds not yet run (leakage-safe)."""
        if round < 1 or round > len(config.CALENDAR):
            return []
        res = self._source.results(year, round, race_index)
        return res if res is not None else []

    def race_results_for_round(self, year: int, round: int) -> dict[str, list[Result]]:
        """Both scored races for a completed round: {'sprint': [...], 'feature': [...]}."""
        return {
            "sprint": self.results(year, round, race_index=0),
            "feature": self.results(year, round, race_index=1),
        }

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Real qualifying order (P1 first) for a round, or ``None`` if not yet run.

        Drives the post-quali forecast: once Friday qualifying is published the
        feature grid is locked and the sprint reverse-grid is determined, so the
        model conditions both race heads on the *actual* grid instead of its
        predicted merit order. ``None`` (pre-quali / no real feed) keeps today's
        predicted-grid behaviour — leakage-safe and never breaking.
        """
        if round < 1 or round > len(config.CALENDAR):
            return None
        q = getattr(self._source, "qualifying", None)
        if q is None:
            return None
        order = q(year, round)
        return list(order) if order else None

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
