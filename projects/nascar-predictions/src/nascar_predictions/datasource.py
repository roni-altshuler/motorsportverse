"""NASCAR data source — calendar/roster from config + snapshots, results from
a selectable feed.

Implements the shared ``motorsport_data.sources.base.DataSource`` contract.
The active season's calendar and roster come from :mod:`config`; archived
seasons resolve their calendar/roster from the per-season snapshots written by
:mod:`backfill` (``data/seasons/<year>.json``) so the historical and playoff
backtests replay real past seasons with the real grids of the time. The
*results* come from a source selected at construction:

- default (``NASCAR_USE_LIVE_RESULTS`` unset/``"0"``): the **real** committed
  snapshots for completed rounds, with the deterministic synthetic generator
  behind them — offline and reproducible, so CI/tests stay deterministic while
  shipping real data;
- live (``NASCAR_USE_LIVE_RESULTS="1"``): a :class:`CompositeNascarSource`
  that hits the cf.nascar.com feeds first, then the snapshot, then synthetic.

The set of *completed* rounds is **derived from the feed** (the leading run of
rounds that actually return results), not a hardcoded constant. Tests can
inject a source directly via ``NascarDataSource(source=...)``.
"""
from __future__ import annotations

import os

from motorsport_data.schema import Competitor, Result, Round, Season, Venue
from motorsport_data.sources.base import DataSource

from . import config
from .sources import CompositeNascarSource


def _live_enabled() -> bool:
    return os.getenv("NASCAR_USE_LIVE_RESULTS", "0") == "1"


class NascarDataSource(DataSource):
    sport = config.SPORT

    def __init__(self, *, live: bool | None = None, source=None):
        if source is not None:
            self._source = source
        elif _live_enabled() if live is None else live:
            self._source = CompositeNascarSource.live()
        else:
            self._source = CompositeNascarSource.default()
        self._completed_cache: dict[int, list[int]] = {}
        self._roster_cache: dict[int, list[dict]] = {}
        # Model-layer memo (Elo replays are expensive); model.py owns the keys.
        self._model_cache: dict = {}

    # ------------------------------------------------------------------ #
    def total_rounds(self, year: int = 0) -> int:
        """Rounds in the season's calendar (config for the active season,
        snapshot for archived ones; falls back to the completed count)."""
        year = year or config.SEASON
        if year == config.SEASON:
            return len(config.CALENDAR)
        cal = self._snapshot_calendar(year)
        if cal:
            return len(cal)
        return len(self.completed_rounds(year))

    def completed_rounds(self, year: int = 0) -> list[int]:
        """Rounds with published results — the leading run of scored rounds.

        Derived from the feed: a round counts as completed once its race
        returns a non-empty classification. Cup rounds complete in date order,
        so we stop at the first round with no results.
        """
        year = year or config.SEASON
        if year not in self._completed_cache:
            limit = len(config.CALENDAR) if year == config.SEASON else 40
            done: list[int] = []
            for rnd in range(1, limit + 1):
                res = self._source.results(year, rnd)
                if res:
                    done.append(rnd)
                else:
                    break
            self._completed_cache[year] = done
        return self._completed_cache[year]

    # ------------------------------------------------------------------ #
    # Roster / teams / makes — season-aware so past seasons replay their real
    # grids.
    # ------------------------------------------------------------------ #
    def roster(self, year: int = 0) -> list[dict]:
        """[{code, name, team, make}] — config for the active season, else
        derived from the season snapshot's rows (the real grid of the time)."""
        year = year or config.SEASON
        if year == config.SEASON:
            return list(config.DRIVERS)
        if year not in self._roster_cache:
            seen: dict[str, dict] = {}
            for rnd in self.completed_rounds(year):
                for r in self.race_rows(year, rnd) or []:
                    # Last round wins, so the roster reflects late-season seats.
                    seen[r["code"]] = {
                        "code": r["code"],
                        "name": r["name"],
                        "team": r["team"],
                        "make": r.get("make", ""),
                    }
            self._roster_cache[year] = list(seen.values())
        return self._roster_cache[year]

    def team_of(self, year: int = 0) -> dict[str, str]:
        year = year or config.SEASON
        if year == config.SEASON:
            return dict(config.TEAM_OF)
        return {d["code"]: d["team"] for d in self.roster(year)}

    def make_of(self, year: int = 0) -> dict[str, str]:
        year = year or config.SEASON
        if year == config.SEASON:
            return dict(config.MAKE_OF)
        return {d["code"]: d.get("make", "") for d in self.roster(year)}

    def driver_name(self, year: int = 0) -> dict[str, str]:
        year = year or config.SEASON
        if year == config.SEASON:
            return dict(config.DRIVER_NAME)
        return {d["code"]: d["name"] for d in self.roster(year)}

    def entrants(self, year: int, round: int) -> list[str]:
        """Codes entered at a round (pre-race public info: the entry list).

        For a completed round the recorded rows ARE the entry list (NASCAR
        classifies every car). For an upcoming round the feed's pre-seeded
        entry list is used when captured; otherwise the season roster.
        """
        rows = self.race_rows(year, round)
        if rows:
            return [r["code"] for r in rows]
        el = getattr(self._source, "entry_list", None)
        if el is not None:
            try:
                entries = el(year, round)
            except Exception:
                entries = None
            if entries:
                return list(entries)
        return [d["code"] for d in self.roster(year)]

    # ------------------------------------------------------------------ #
    def season(self, year: int = 0) -> Season:
        year = year or config.SEASON
        return Season(
            sport=config.SPORT,
            year=year,
            competitors=[
                Competitor(code=d["code"], name=d["name"], team=d["team"])
                for d in self.roster(year)
            ],
            teams=config.TEAMS if year == config.SEASON else [],
            calendar=config.CALENDAR if year == config.SEASON else [],
            completed_rounds=self.completed_rounds(year),
        )

    def round(self, year: int, round: int) -> Round:
        venue = self._venue(round, year)
        completed = round in self.completed_rounds(year)
        results = self.results(year, round) if completed else []
        return Round(season=year, round=round, venue=venue, completed=completed, results=results)

    def results(self, year: int, round: int) -> list[Result]:
        """Classified order for a scored race. Returns ``[]`` for rounds not
        yet run (leakage-safe)."""
        if round < 1:
            return []
        if year == config.SEASON and round > len(config.CALENDAR):
            return []
        res = self._source.results(year, round)
        return res if res is not None else []

    def race_results_for_round(self, year: int, round: int) -> dict[str, list[Result]]:
        """The round's scored race keyed by race type: {'race': [...]}.

        Cup rounds run one points race; the dict shape keeps parity with the
        multi-race feeder-series projects so shared tooling reads one contract.
        """
        return {"race": self.results(year, round)}

    def race_rows(self, year: int, round: int) -> list[dict] | None:
        """Full rows (every classified car with grid/status/points/laps) when
        a real source carries them; None in synthetic-only mode."""
        rr = getattr(self._source, "race_rows", None)
        return rr(year, round) if rr else None

    def stage_results(self, year: int, round: int) -> dict[str, list[dict]] | None:
        """Per-stage top-10 rows ({"1": [...], "2": [...]}), or None."""
        sr = getattr(self._source, "stage_results", None)
        return sr(year, round) if sr else None

    def qualifying(self, year: int, round: int) -> list[str] | None:
        """Real qualifying order (P1 first) for a round, or ``None`` if not
        run. Drives the post-quali forecast — leakage-safe (``None`` keeps the
        predicted-grid behaviour)."""
        if round < 1:
            return None
        if year == config.SEASON and round > len(config.CALENDAR):
            return None
        q = getattr(self._source, "qualifying", None)
        if q is None:
            return None
        order = q(year, round)
        return list(order) if order else None

    def provenance(self, year: int, round: int) -> str:
        """Which source served this race's results — 'snapshot' |
        'nascar-feed' | 'synthetic'. Used by the honest calibration gate to
        count only *real* rounds."""
        src = self._source
        if hasattr(src, "provenance"):
            return src.provenance(year, round)
        return getattr(src, "name", "synthetic")

    # ------------------------------------------------------------------ #
    def _snapshot_calendar(self, year: int) -> list[dict]:
        for src in getattr(self._source, "_sources", [self._source]):
            cal = getattr(src, "calendar", None)
            if cal is None:
                continue
            try:
                entries = cal(year)
            except Exception:
                entries = []
            if entries:
                return entries
        return []

    def _venue(self, round: int, year: int = 0) -> Venue:
        year = year or config.SEASON
        if year == config.SEASON:
            idx = round - 1
            return config.CALENDAR[idx] if 0 <= idx < len(config.CALENDAR) else config.CALENDAR[0]
        for c in self._snapshot_calendar(year):
            if int(c.get("round", 0)) == round:
                return Venue(
                    key=c.get("key", f"round-{round}"),
                    name=c.get("track", c.get("name", f"Round {round}")),
                    country=c.get("country", "United States"),
                    kind=c.get("kind", "oval"),
                )
        return Venue(key=f"round-{round}", name=f"Round {round}", kind="oval")

    def venue_for(self, year: int, round: int) -> Venue:
        """Public venue accessor (season-aware)."""
        return self._venue(round, year)

    def track_type_for(self, year: int, round: int) -> str:
        """The round's track type — THE model/calibration stratum."""
        if year == config.SEASON:
            meta = config.CALENDAR_META.get(round, {})
            if meta.get("trackType"):
                return meta["trackType"]
        for c in self._snapshot_calendar(year):
            if int(c.get("round", 0)) == round:
                if c.get("trackType"):
                    return c["trackType"]
                return config.track_type_of(c.get("track", c.get("name", "")), year)
        return "intermediate"

    def race_meta(self, year: int, round: int) -> dict:
        """Calendar metadata dict for a round (config or snapshot)."""
        if year == config.SEASON and round in config.CALENDAR_META:
            return dict(config.CALENDAR_META[round])
        for c in self._snapshot_calendar(year):
            if int(c.get("round", 0)) == round:
                return dict(c)
        return {"round": round}


# Back-compat alias for the scaffolded template name.
SportDataSource = NascarDataSource
