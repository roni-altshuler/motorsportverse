"""MotoGP data source — calendar/roster from config, results from the snapshots.

Implements the shared :class:`motorsport_data.sources.base.DataSource` contract
(the same shape F1/F2/F3 satisfy) so the reused model/pipeline see a MotoGP
weekend exactly like any other series: two scored races per round (0 = Sprint,
1 = Grand Prix), a real qualifying grid, and a completed-set derived from the
feed rather than the wall clock.

Beyond the base contract it adds :meth:`history_events` — the leakage-safe
cross-season replay the Elo skill model seeds from (riders carry form year to
year, unlike a fresh F3 grid).
"""
from __future__ import annotations

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config
from .sources.snapshot import SnapshotMotoGPSource

SPRINT_INDEX = 0
FEATURE_INDEX = 1


class MotoGPDataSource(DataSource):
    sport = config.SPORT

    def __init__(self, *, source=None):
        self._source = source or SnapshotMotoGPSource()

    # ------------------------------------------------------------------ #
    def completed_rounds(self, year: int = config.SEASON) -> list[int]:
        done = self._source.completed_rounds(year)
        if done:
            return sorted(done)
        # fall back to deriving from the feed (leading run of scored rounds)
        out: list[int] = []
        for rnd in range(1, len(config.CALENDAR) + 1):
            if self._source.results(year, rnd, FEATURE_INDEX):
                out.append(rnd)
            else:
                break
        return out

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

    def results(self, year: int, round: int, race_index: int = FEATURE_INDEX) -> list[Result]:
        if round < 1 or round > len(config.CALENDAR):
            return []
        res = self._source.results(year, round, race_index)
        return res if res is not None else []

    def race_results_for_round(self, year: int, round: int) -> dict[str, list[Result]]:
        return {
            "sprint": self.results(year, round, SPRINT_INDEX),
            "feature": self.results(year, round, FEATURE_INDEX),
        }

    def qualifying(self, year: int, round: int) -> list[str] | None:
        if round < 1 or round > len(config.CALENDAR):
            return None
        q = getattr(self._source, "qualifying", None)
        if q is None:
            return None
        order = q(year, round)
        return list(order) if order else None

    def provenance(self, year: int, round: int, race_index: int = FEATURE_INDEX) -> str:
        src = self._source
        if hasattr(src, "provenance"):
            return src.provenance(year, round, race_index)
        return getattr(src, "name", "snapshot")

    # ------------------------------------------------------------------ #
    def history_events(self, up_to_year: int, up_to_round: int) -> list[tuple[int, int, str, dict]]:
        """Every scored (season, sub-round, race_type, results) strictly before the
        cutoff, oldest first — the cross-season corpus the Elo model replays.

        Prior *seasons* (config.HISTORY_SEASONS) are admitted whole; the current
        season is admitted up to ``up_to_round`` exclusive. Leakage-safe by
        construction: nothing at or after the forecast round is returned.
        """
        events: list[tuple[int, int, str, dict]] = []
        seasons = [y for y in config.HISTORY_SEASONS if y < up_to_year] + [up_to_year]
        for y in seasons:
            snap = config.load_snapshot(y)
            if not snap:
                continue
            last = (up_to_round - 1) if y == up_to_year else len(snap.get("results", {}))
            for rnd in range(1, int(last) + 1):
                for sub, race_type, idx in ((2 * rnd - 1, "sprint", SPRINT_INDEX),
                                            (2 * rnd, "feature", FEATURE_INDEX)):
                    res = self._source.results(y, rnd, idx)
                    if res:
                        events.append((y, sub, race_type, {r.competitor: r.position for r in res}))
        return events

    def _venue(self, round: int) -> Venue:
        return config.venue_for(round)
