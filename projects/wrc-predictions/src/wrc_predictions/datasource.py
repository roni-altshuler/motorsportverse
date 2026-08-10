"""WRC data source — calendar/roster from config, rally results from the snapshots.

Implements the shared :class:`motorsport_data.sources.base.DataSource` contract.
A WRC round is one rally = one classification (no sprint, no qualifying grid), so
this is simpler than a circuit weekend. Beyond the base contract it adds
:meth:`history_events` (leakage-safe cross-season replay for the Elo skill model)
and :meth:`surface_history` (per-driver same-surface finishing form — the
rally-specific signal).
"""
from __future__ import annotations

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config
from .sources.snapshot import SnapshotWrcSource


class WrcDataSource(DataSource):
    sport = config.SPORT

    def __init__(self, *, source=None):
        self._source = source or SnapshotWrcSource()

    def completed_rounds(self, year: int = config.SEASON) -> list[int]:
        done = self._source.completed_rounds(year)
        if done:
            return sorted(done)
        out: list[int] = []
        for rnd in range(1, len(config.CALENDAR) + 1):
            if self._source.results(year, rnd):
                out.append(rnd)
        return sorted(out)

    def season(self, year: int = config.SEASON) -> Season:
        return Season(
            sport=config.SPORT, year=year,
            competitors=[Competitor(code=d["code"], name=d["name"], team=d["team"])
                         for d in config.DRIVERS],
            teams=config.TEAMS, calendar=config.CALENDAR,
            completed_rounds=self.completed_rounds(year),
        )

    def round(self, year: int, round: int) -> Round:
        venue = self._venue(round)
        completed = round in self.completed_rounds(year)
        results = self.results(year, round) if completed else []
        return Round(season=year, round=round, venue=venue, completed=completed, results=results)

    def results(self, year: int, round: int) -> list[Result]:
        if round < 1 or round > len(config.CALENDAR):
            return []
        res = self._source.results(year, round)
        return res if res is not None else []

    def provenance(self, year: int, round: int) -> str:
        src = self._source
        return src.provenance(year, round) if hasattr(src, "provenance") else "snapshot"

    # ------------------------------------------------------------------ #
    def history_events(self, up_to_year: int, up_to_round: int) -> list[tuple[int, int, dict]]:
        """Every scored (season, round, {code: position}) strictly before the
        cutoff, oldest first — the cross-season corpus the Elo model replays.

        A rally is one event, so the (season, round) ordering is already
        chronological and leakage-safe by construction.
        """
        events: list[tuple[int, int, dict]] = []
        seasons = [y for y in config.HISTORY_SEASONS if y < up_to_year] + [up_to_year]
        for y in seasons:
            snap = config.load_snapshot(y)
            if not snap:
                continue
            last = (up_to_round - 1) if y == up_to_year else snap.get("totalRounds", 0)
            for rnd in range(1, int(last) + 1):
                res = self._source.results(y, rnd)
                if res:
                    events.append((y, rnd, {r.competitor: r.position for r in res}))
        return events

    def surface_history(self, up_to_year: int, up_to_round: int) -> dict[str, dict[str, list[int]]]:
        """{surface: {code: [finishing positions]}} over prior rallies — the
        leakage-safe same-surface form signal. Reads each prior season's snapshot
        calendar for the surface of each completed round."""
        out: dict[str, dict[str, list[int]]] = {}
        seasons = [y for y in config.HISTORY_SEASONS if y < up_to_year] + [up_to_year]
        for y in seasons:
            snap = config.load_snapshot(y)
            if not snap:
                continue
            surf_of = {int(c["round"]): (c.get("surface") or "gravel")
                       for c in snap.get("calendar", [])}
            last = (up_to_round - 1) if y == up_to_year else snap.get("totalRounds", 0)
            for rnd in range(1, int(last) + 1):
                res = self._source.results(y, rnd)
                if not res:
                    continue
                surf = surf_of.get(rnd, "gravel")
                bucket = out.setdefault(surf, {})
                for r in res:
                    bucket.setdefault(r.competitor, []).append(r.position)
        return out

    def _venue(self, round: int) -> Venue:
        return config.venue_for(round)
